#!/usr/bin/env python3
from __future__ import annotations                      # noqa: F404

import os
import shutil
from typing import Dict, List
import yaml
import re
import urllib.request

from pathlib import Path
from multiprocessing import Pool, Manager
from itertools import repeat

import rdbox_app_market.config
from rdbox_app_market.util import Util
from rdbox_app_market.helm import HelmCommand
from rdbox_app_market.github import GithubRepos, RdboxGithubRepos, ReferenceGithubRepos
from rdbox_app_market.values_yaml import ValuesYaml

from logging import getLogger
r_logger = getLogger('rdbox_cli')
r_print = getLogger('rdbox_cli').getChild("stdout")


class Collector(object):
    """ This instance will collect Helm Charts from the specified GitHub repository.

    Also, if the format is not specified, the Chart will be excluded.
    """
    def __init__(self, src_repos: ReferenceGithubRepos, dst_repo: RdboxGithubRepos):
        """ constructor

        Args:
            src_repos (list[ReferenceGithubRepos]): List of Git repositories to reference when generating a Helm Chart for RDBOX
            dst_repo (RdboxGithubRepos): The output destination GitHub repository.
        """
        self.src_repos = src_repos
        self.rdbox_master_repo = dst_repo

    def work(self) -> tuple[ChartInSpecificDir]:
        """Do the work

        Returns:
            Tuple[ChartInSpecificDir, ChartInSpecificDir]: 1st is Non-dependent charts. 2nd is Charts with dependencies.
        """
        chart_in_specific_dir = ChartInSpecificDir(self.rdbox_master_repo, ChartInSpecificDir.ANNOTATION_OTHERS)
        for repo in self.src_repos:
            r_print.info('------------------- {url} ------------------'.format(url=repo.get_url()))
            ref_chart_in_specific_dir = ChartInSpecificDir(repo, ChartInSpecificDir.ANNOTATION_OTHERS)
            now_processing_isolations, now_processing_dependons = ref_chart_in_specific_dir.preprocessing()
            chart_in_specific_dir.merge(now_processing_isolations)
            chart_in_specific_dir.merge(now_processing_dependons)
        chart_in_specific_dir.move_entity()
        ################
        isolations_collect_result, dependons_collect_result = chart_in_specific_dir.preprocessing()
        return isolations_collect_result, dependons_collect_result


class Publisher(object):
    """ The Instance is to arrange the converting and publish of helm chart.

    like a publishing company.
    """
    def __init__(self, isolations: ChartInSpecificDir, dependons: ChartInSpecificDir, dest_repo: RdboxGithubRepos):
        """ constructor

        Args:
            isolations (ChartInSpecificDir): Chart that is independent of other Charts.
            dependons (ChartInSpecificDir): Chart that depend on other Charts.
            dst_repo (RdboxGithubRepos): The output destination GitHub repository.
        """
        self.isolations = isolations
        self.dependons = dependons
        self.rdbox_gh_repo = dest_repo

    def work(self, exec_publish: bool) -> ChartInSpecificDir:
        """Do the work

        Args:
            exec_publish (bool): Do you want to publish it?

        - convert
            - specify_nodeSelector_for_rdbox
            - Scraping icon images
            - customize_chartyaml_for_rdbox
            - helm_command.template
            - helm_command.package
        - pack
            - helm_command.repo_index
            - commit
        - publish
            - push

        Returns:
            ChartInSpecificDir: Information about the Helm Chart to be published in the RDBOX App Market.
        """
        r_print.info('------------------- {url} ------------------'.format(url=self.rdbox_gh_repo.get_url()))
        #########
        invalid_key_list = self.isolations.convert(self.rdbox_gh_repo)
        self.dependons.remove_by_depend_modules_list(invalid_key_list)
        _ = self.dependons.convert(self.rdbox_gh_repo)
        #########
        rdbox_app_market_all_chart = self.dependons.merge(self.isolations)
        rdbox_app_market_all_chart.publish(self.rdbox_gh_repo, exec_publish)
        return rdbox_app_market_all_chart


class ChartInSpecificDirConverError(Exception):
    pass


class ChartInSpecificDirPackError(Exception):
    pass


class ChartInSpecificDir(object):

    ANNOTATION_OTHERS = 'others'
    ANNOTATION_ISOLATIONS = 'isolations'
    ANNOTATION_DEPENDONS = 'dependons'

    def __init__(self, repo: GithubRepos, annotation=ANNOTATION_OTHERS):
        """Constructor

        Args:
            repo (GithubRepos): GitHub repositories to reference.
            annotation (str, optional): The classification of the data held by GitHub repositories when it is classified.
        """
        self.repo = repo
        if annotation == ChartInSpecificDir.ANNOTATION_OTHERS or \
            annotation == ChartInSpecificDir.ANNOTATION_ISOLATIONS or \
                annotation == ChartInSpecificDir.ANNOTATION_DEPENDONS:
            self.annotation = annotation
        else:
            raise ValueError
        self.specific_dirpath = self.repo.get_dirpath_with_prefix()
        manager = Manager()
        self.all_HelmModule_mapped_by_module_name = manager.dict()
        self.all_packaged_tgz_path_mapped_by_module_name = manager.dict()

    def __repr__(self):
        return str(self.get_all_HelmModule_mapped_by_module_name())

    def get_repo(self) -> GithubRepos:
        """Get the Git repository that manages this directory.

        Returns:
            GithubRepos: The Git repository that manages this directory.
        """
        return self.repo

    def get_annotation(self) -> str:
        """Get annotation string

        - others, isolations, dependons

        Returns:
            str: annotation string.
        """
        return self.annotation

    def get_specific_dirpath(self) -> str:
        """Get the directory path where the chart is stored (full path)

        Returns:
            str: The directory path where the chart is stored (full path)
        """
        return self.specific_dirpath

    def get_all_HelmModule_mapped_by_module_name(self) -> dict[str, HelmModule]:
        """Get all HelmModule mapped by module_name.

        Returns:
            dict[str, HelmModule]: all HelmModule mapped by module_name.
        """
        return self.all_HelmModule_mapped_by_module_name

    def get_all_packaged_tgz_path_mapped_by_module_name(self) -> dict[str, str]:
        """Get all packaged tgz path mapped by module_name.

        Returns:
            dict[str, str]: All packaged tgz path mapped by module_name.
        """
        return self.all_packaged_tgz_path_mapped_by_module_name

    def merge(self, other: ChartInSpecificDir) -> ChartInSpecificDir:
        """Update the contents of the dictionary with other keys and values.

        The content is overwritten according to the priority order.

        Args:
            other (ChartInSpecificDir): Other Instance.

        Returns:
            ChartInSpecificDir: This Instance.
        """
        for module_name, helm_module in other.get_all_HelmModule_mapped_by_module_name().items():
            if module_name in self.get_all_HelmModule_mapped_by_module_name():
                if helm_module.get_priority() >= self.get_all_HelmModule_mapped_by_module_name()[module_name].get_priority():
                    self.get_all_HelmModule_mapped_by_module_name()[module_name] = helm_module
                    if module_name in other.get_all_packaged_tgz_path_mapped_by_module_name():
                        self.get_all_packaged_tgz_path_mapped_by_module_name().setdefault(module_name, other.get_all_packaged_tgz_path_mapped_by_module_name()[module_name])
                else:
                    continue
            else:
                self.get_all_HelmModule_mapped_by_module_name().setdefault(module_name, helm_module)
                if module_name in other.get_all_packaged_tgz_path_mapped_by_module_name():
                    self.get_all_packaged_tgz_path_mapped_by_module_name().setdefault(module_name, other.get_all_packaged_tgz_path_mapped_by_module_name()[module_name])
        return self

    def move_entity(self) -> None:
        """Move the entity (file or directory) of the helm chart to the directory where this instant is managed.
        """
        for module_name, helm_module in self.get_all_HelmModule_mapped_by_module_name().items():
            path = os.path.join(self.get_specific_dirpath(), module_name)
            try:
                shutil.rmtree(path)
            except FileNotFoundError:
                pass
            try:
                shutil.copytree(helm_module.get_module_dir_path(), path)
            except Exception:
                import traceback
                r_logger.warning(traceback.format_exc())

    def preprocessing(self) -> tuple[ChartInSpecificDir]:
        """Pre-processing before converting to charts for RDBOX App Market.

        - Filtering Charts with Unknown Dependencies.
            - Separate charts with dependencies and charts without dependencies.
        - Filter out charts that do not meet the specifications.
            - Can't select a nodeSelector.
            - Bad image key structure
            - deprecated image

        Returns:
            Tuple[ChartInSpecificDir, ChartInSpecificDir]: 1st is Non-dependent charts. 2nd is Charts with dependencies.
        """
        self.all_HelmModule_mapped_by_module_name = self.get_HelmModule_all()
        ########
        isolations_collect_result, dependons_collect_result = self.__split_module_by_dependencies()
        if self.get_repo().is_manually_repo():
            isolations_collect_result = ChartInSpecificDir(self.repo, ChartInSpecificDir.ANNOTATION_ISOLATIONS).__update(isolations_collect_result)
            dependons_collect_result = ChartInSpecificDir(self.repo, ChartInSpecificDir.ANNOTATION_DEPENDONS).__update(dependons_collect_result)
        else:
            isolations_collect_result, dependons_collect_result = self.__excludes_unknown_dependencies(isolations_collect_result, dependons_collect_result)
        ########
        invalid_key_list = isolations_collect_result.__get_invalid_key_list()
        isolations_collect_result.remove_by_key_list(invalid_key_list)
        dependons_collect_result.remove_by_depend_modules_list(invalid_key_list)
        ########
        invalid_key_list = dependons_collect_result.__get_invalid_key_list()
        dependons_collect_result.remove_by_key_list(invalid_key_list)
        ########
        return isolations_collect_result, dependons_collect_result

    def convert(self, repo_for_rdbox: GithubRepos) -> list[str]:
        """Convert to RDBOX App Market chart.

        Args:
            repo_for_rdbox (GithubRepos): Github repository (like gh-pages) for publishing RDBOX App Market

        Returns:
            list[str]: List of module names that failed to be converted.
        """
        invalid_key_list = []
        p = Pool(int(os.cpu_count() * float(rdbox_app_market.config.get('rdbox', 'maximum_cpu_usage'))))
        result = p.starmap(self.convert_detail, zip(repeat(repo_for_rdbox), self.get_all_HelmModule_mapped_by_module_name().keys(), self.get_all_HelmModule_mapped_by_module_name().values()))
        for invalids in result:
            invalid_key_list.extend(invalids)
        for module_name in invalid_key_list:
            r_print.info('Delete(MISS_CONVERT): ' + module_name)
        self.remove_by_key_list(invalid_key_list)
        return list(set(invalid_key_list))

    def publish(self, rdbox_gh_repo: GithubRepos, exec_publish: bool) -> list[str]:
        """Push (publish) the corresponding Git repository in order to make it presentable for publishing helm charts.

        Args:
            rdbox_gh_repo (GithubRepos): Github repository (like gh-pages) for publishing RDBOX App Market
            exec_publish (bool): Do you want to publish it?

        Returns:
            list[str]: List of module names that failed to be published.
        """
        invalid_key_list = []
        try:
            self.__pack(rdbox_gh_repo)
            if exec_publish:
                self.__publish(rdbox_gh_repo)
        except ChartInSpecificDirPackError:
            import traceback
            r_logger.warning(traceback.format_exc())
            invalid_key_list.extend(self.get_all_HelmModule_mapped_by_module_name().keys())
        except Exception:
            import traceback
            r_logger.warning(traceback.format_exc())
            invalid_key_list.extend(self.get_all_HelmModule_mapped_by_module_name().keys())
        self.remove_by_key_list(invalid_key_list)
        return list(set(invalid_key_list))

    def remove_by_key_list(self, module_name_list: list[str]) -> None:
        """The Helm chart information of the specified module name is removed from the managed object.

        Args:
            module_name_list (list[str]): List of module names to be removed.
        """
        for key in list(set(module_name_list)):
            # self.__delete_entity_by_module_name(key)
            self.all_HelmModule_mapped_by_module_name.pop(key)

    def remove_by_depend_modules_list(self, module_name_list: list[str]) -> None:
        """If the specified list of modules contains a dependent module, exclude the chart from being managed.

        - This is only valid for charts that have dependencies.

        Args:
            module_name_list (list[str]): List of dependent modules to be verified.
        """
        del_keys = []
        for depend_module_name in module_name_list:
            for module_name, helm_module in self.get_all_HelmModule_mapped_by_module_name().items():
                if helm_module.has_module_of_dependencies(depend_module_name):
                    del_keys.append(module_name)
        for key in list(set(del_keys)):
            r_print.info('Delete(INVALID_DEP): ' + key)
            self.__delete_entity_by_module_name(key)
            self.all_HelmModule_mapped_by_module_name.pop(key)

    def get_HelmModule_all(self) -> Dict[str, HelmModule]:
        """Retrieve HelmModules stored in a specific directory as a map.

        Returns:
            Dict[str, HelmModule]: HelmModule() mapped to a module_name.
        """
        module_mapping_data = {}
        _module_list = self.__get_module_list()
        for module_name in _module_list:
            if os.path.isfile(os.path.join(self.get_specific_dirpath(), module_name, 'values.yaml')):
                helm_module = HelmModule(self.get_specific_dirpath(), module_name, self.repo.get_priority())
                module_mapping_data.setdefault(module_name, helm_module)
        return module_mapping_data

    def convert_detail(self, repo_for_rdbox: GithubRepos, module_name: str, helm_module: HelmModule) -> List[str]:
        """Performs various conversions for app_market. Returns a list of module names that failed to be converted.

        Args:
            repo_for_rdbox (GithubRepos): Github repository (like gh-pages) for publishing RDBOX App Market
            module_name (str): The module name of the chart to be processed.
            helm_module (HelmModule): A class representing the chart to be processed.

        Returns:
            List[str]: List of module names that failed to be converted.
        """
        invalid_key_list = []
        try:
            # Core Processing
            if self.get_repo().is_manually_repo():
                self.__specify_chart_yaml(module_name, helm_module)
                self.__generate_package_tgz(module_name, helm_module)
            else:
                self.__specify_values_yaml(module_name, helm_module)
                self.__specify_chart_yaml(module_name, helm_module)
                self.__resolve_dependencies_based_on_requirements_yaml(repo_for_rdbox, module_name, helm_module)
                self.__generate_package_tgz(module_name, helm_module)
            # Logging
            if self.get_annotation() == ChartInSpecificDir.ANNOTATION_ISOLATIONS:
                r_print.info("Convert(ISOLATIONS): " + module_name)
            elif self.get_annotation() == ChartInSpecificDir.ANNOTATION_DEPENDONS:
                r_print.info("Convert(DEPENDONS): " + module_name)
        except ChartInSpecificDirConverError as e:
            invalid_key_list.append(module_name)
            r_print.info("ConvertERR({msg}): {module_name}".format(msg=str(e), module_name=module_name))
            import traceback
            r_logger.warning(traceback.format_exc())
        except Exception as e:
            invalid_key_list.append(module_name)
            r_print.info("ConvertERR({msg}): {module_name}".format(msg=str(e), module_name=module_name))
            import traceback
            r_logger.warning(traceback.format_exc())
        finally:
            return invalid_key_list

    def __specify_values_yaml(self, module_name: str, helm_module: HelmModule):
        multi_arch_dict = {}
        # Continue even if it fails.
        try:
            helm_module.specify_storageClass_for_rdbox()
            helm_module.specify_ingress_for_rdbox()
        except Exception:
            import traceback
            r_logger.warning(traceback.format_exc())
        # Stop even if it fails.
        try:
            _, _, multi_arch_dict = helm_module.specify_nodeSelector_for_rdbox()
            if len(multi_arch_dict.keys()) > 0:
                r_logger.debug('It has Multi Arch Image. ' + module_name)
                r_logger.debug(multi_arch_dict)
        except Exception:
            import traceback
            r_logger.warning(traceback.format_exc())
            raise ChartInSpecificDirConverError('Error in specify_nodeSelector_for_rdbox')

    def __specify_chart_yaml(self, module_name: str, helm_module: HelmModule):
        dir_to_save_icon = os.path.join(self.repo.get_dirpath(), 'icons')
        os.makedirs(dir_to_save_icon, exist_ok=True)
        helm_module.customize_chartyaml_for_rdbox(dir_to_save_icon)

    def __resolve_dependencies_based_on_requirements_yaml(self, repo_for_rdbox: GithubRepos, module_name: str, helm_module: HelmModule):
        if self.get_annotation() == ChartInSpecificDir.ANNOTATION_DEPENDONS:
            helm_module.resolve_dependencies_based_on_requirements_yaml(repo_for_rdbox)

    def __generate_package_tgz(self, module_name: str, helm_module: HelmModule):
        helm_command = HelmCommand()
        if self.get_repo().is_manually_repo():
            helm_command.dep_update(self.get_specific_dirpath(), module_name)
            helm_module.get_RequirementsYaml().remove_lock_file()
        # Verify Format
        manifest_map = helm_command.template(self.get_specific_dirpath(), module_name, helm_module.extract_set_options_from_install_command())
        if not self.__is_correct_manifest_map(manifest_map):
            raise ChartInSpecificDirConverError('Contains workloads (Pods, Deployment, DaemonSet, etc.) for which nodeSelector is not specified.')
        # Generate Package
        path_of_generation_result = helm_command.package(self.get_specific_dirpath(), module_name, self.get_specific_dirpath())
        if os.path.isfile(path_of_generation_result):
            self.all_packaged_tgz_path_mapped_by_module_name[module_name] = path_of_generation_result
        else:
            raise ChartInSpecificDirConverError(path_of_generation_result)

    def __pack(self, rdbox_gh_repo):
        helm_command = HelmCommand()
        path_of_generation_result = helm_command.repo_index(self.get_specific_dirpath())
        if os.path.isfile(path_of_generation_result):
            target = os.path.join(rdbox_gh_repo.get_dirpath_with_prefix(), os.path.basename(path_of_generation_result))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.move(path_of_generation_result, target)
        else:
            raise ChartInSpecificDirPackError(path_of_generation_result)
        for _, path in self.all_packaged_tgz_path_mapped_by_module_name.items():
            target = os.path.join(rdbox_gh_repo.get_dirpath_with_prefix(), os.path.basename(path))
            shutil.move(path, target)
        # for gh-pages
        rdbox_gh_repo.commit()
        r_print.info('commit gh-pages')
        # for master
        self.get_repo().commit()
        r_print.info('commit master')

    def __publish(self, rdbox_gh_repo):
        try:
            # for gh-pages
            rdbox_gh_repo.push()
            r_print.info('push origin gh-pages')
            # for master
            self.get_repo().push()
            r_print.info('push origin master')
        except Exception:
            import traceback
            r_logger.warning(traceback.format_exc())

    def __update(self, all_RequirementsYaml_mapped_by_module_name):
        """Overwrite with dict(all_RequirementsYaml_mapped_by_module_name).

        Args:
            all_RequirementsYaml_mapped_by_module_name (dict[str, HelmModule]): All requirements.yaml mapped by module_name.

        Returns:
            ChartInSpecificDir: This instance.
        """
        self.all_HelmModule_mapped_by_module_name.update(all_RequirementsYaml_mapped_by_module_name)
        return self

    def __is_correct_manifest_map(self, manifest_map):
        flg = True
        for filename, manifest in manifest_map.items():
            if manifest is None:
                continue
            if manifest.get('kind') in ['Pod', 'Deployment', 'Job', 'DaemonSet', 'ReplicaSet', 'StatefulSet']:
                node_selector = Util.has_key_recursion(manifest, 'nodeSelector')
                if node_selector is None:
                    if 'test' in filename:
                        flg = True
                    else:
                        r_logger.debug(filename)
                        r_logger.debug(yaml.dump(manifest))
                        # TODO: Provisional support
                        # It may be missing. 'helm template .' command.
                        if self.get_annotation() == ChartInSpecificDir.ANNOTATION_ISOLATIONS:
                            flg = False
                            break
                else:
                    flg = True
            else:
                continue
        return flg

    def __split_module_by_dependencies(self):
        isolations = {}      # An independent helm chart on which no other dependencies exist.
        dependons = {}       # Other helm chart-dependent modules.
        for module_name, helm_module in self.get_all_HelmModule_mapped_by_module_name().items():
            if helm_module.get_full_path_to_requirements_yaml() is None:
                isolations.setdefault(module_name, helm_module)
            else:
                dependons.setdefault(module_name, helm_module)
        return isolations, dependons

    def __excludes_unknown_dependencies(self, isolations, dependons):
        # candidate for deletion
        candidate = []
        for module_name, helm_module in dependons.items():
            for req_obj in helm_module.get_RequirementObject_list():
                candidate.append(req_obj.name)
        candidate = list(set(candidate))
        del_keys = []
        for candidate_module_name in candidate:
            if (candidate_module_name not in isolations) and (candidate_module_name not in dependons):
                for module_name, helm_module in dependons.items():
                    if helm_module.has_module_of_dependencies(candidate_module_name):
                        del_keys.append(module_name)
        for key in list(set(del_keys)):
            r_print.info('Delete(UNKNOWN_DEP): ' + key)
            self.__delete_entity_by_module_name(key)
            dependons.pop(key)
        return (ChartInSpecificDir(self.repo, ChartInSpecificDir.ANNOTATION_ISOLATIONS).__update(isolations),
                ChartInSpecificDir(self.repo, ChartInSpecificDir.ANNOTATION_DEPENDONS).__update(dependons))

    def __delete_entity_by_module_name(self, module_name):
        dir_path = os.path.join(self.get_specific_dirpath(), module_name)
        try:
            shutil.rmtree(dir_path)
        except FileNotFoundError:
            pass

    def __get_invalid_key_list(self):
        invalid_keys = []
        not_has_key_nodeSelector = self.__filter_nodeselector()
        invalid_imagetag = self.__filter_valuesyaml_imagetag()
        deprecated = self.__filter_deprecate()
        invalid_keys += not_has_key_nodeSelector
        invalid_keys += invalid_imagetag
        invalid_keys += deprecated
        if self.repo.get_check_tldr():
            tldr = self.__filter_tldr()
            invalid_keys += tldr
        return list(set(invalid_keys))

    def __filter_nodeselector(self):
        invalid_module = {}
        for module_name, helm_module in self.get_all_HelmModule_mapped_by_module_name().items():
            # Special support for bitnami.
            if (module_name == 'common') and helm_module.is_contain_bitnami_string():
                continue
            if helm_module.has_active_nodeSelector() is False:
                invalid_module.setdefault(module_name, helm_module)
        # Bail out the commented out nodeSelector.
        list_of_module_names_that_fixed_nodeSelector = []
        for module_name, helm_module in invalid_module.items():
            if helm_module.has_commentout_nodeSelector():
                try:
                    helm_module.correct_commentout_nodeSelector()
                    r_print.info("Modify(nodeSelector): " + module_name)
                    list_of_module_names_that_fixed_nodeSelector.append(module_name)
                except Exception:
                    pass
        for module_name in list_of_module_names_that_fixed_nodeSelector:
            invalid_module.pop(module_name)
        for module_name in list(set(invalid_module.keys())):
            r_print.info('Delete(nodeSelector): ' + module_name)
        return list(set(invalid_module.keys()))

    def __filter_valuesyaml_imagetag(self):
        invalid_module = []
        for module_name, helm_module in self.get_all_HelmModule_mapped_by_module_name().items():
            # Special support for bitnami.
            if (module_name == 'common') and helm_module.is_contain_bitnami_string():
                continue
            if helm_module.has_expected_structure_for_imagetag() is False:
                invalid_module.append(module_name)
        for module_name in list(set(invalid_module)):
            r_print.info('Delete(imageTag): ' + module_name)
        return list(set(invalid_module))

    def __filter_deprecate(self):
        invalid_module = []
        for module_name, helm_module in self.get_all_HelmModule_mapped_by_module_name().items():
            if helm_module.is_contain_deprecate_string_at_head():
                invalid_module.append(module_name)
        for module_name in list(set(invalid_module)):
            r_print.info('Delete(deprecate): ' + module_name)
        return list(set(invalid_module))

    def __filter_tldr(self):
        invalid_module = []
        for module_name, helm_module in self.get_all_HelmModule_mapped_by_module_name().items():
            # Special support for bitnami.
            if (module_name == 'common') and helm_module.is_contain_bitnami_string():
                continue
            if helm_module.is_contain_tldr_string() is False:
                invalid_module.append(module_name)
        for module_name in list(set(invalid_module)):
            r_print.info('Delete(TLDR): ' + module_name)
        return list(set(invalid_module))

    def __get_module_list(self):
        stable_module_path = self.repo.get_dirpath_with_prefix()
        li = os.listdir(stable_module_path)
        return li


class HelmModule(object):
    def __init__(self, specific_dir_path, module_name, priority):
        self.module_name = module_name
        self.specific_dir_path = specific_dir_path
        self.module_dir_path = os.path.join(specific_dir_path, module_name)
        self.priority = priority
        # Original Object
        self.requirements_yaml = RequirementsYaml(self.module_dir_path, module_name)
        self.values_yaml = ValuesYaml(self.module_dir_path, module_name)
        self.readme_md = ReadmeMd(self.module_dir_path, module_name)
        self.chart_yaml = ChartYaml(self.module_dir_path, module_name)

    def __repr__(self):
        return str(self.requirements_yaml)

    # Getter(Props) #
    def get_module_name(self):
        return self.module_name

    def get_module_dir_path(self):
        return self.module_dir_path

    def get_priority(self):
        return self.priority
    #################

    # Getter(Files) #
    def get_RequirementsYaml(self):
        return self.requirements_yaml

    def get_ValuesYaml(self):
        return self.values_yaml

    def get_ReadmeMd(self):
        return self.readme_md

    def get_ChartYaml(self):
        return self.chart_yaml
    #################

    def resolve_dependencies_based_on_requirements_yaml(self, repo_for_rdbox):
        self.get_RequirementsYaml().specify_repository_for_rdbox(repo_for_rdbox)
        self.get_RequirementsYaml().dump()
        self.get_RequirementsYaml().remove_lock_file()
        self.get_RequirementsYaml().setup_charts_dir()

    def has_module_of_dependencies(self, module_name):
        return self.get_RequirementsYaml().has_module_of_dependencies(module_name)

    def get_RequirementObject_list(self):
        return self.get_RequirementsYaml().get_RequirementObject_list()

    def get_full_path_to_requirements_yaml(self):
        return self.get_RequirementsYaml().get_full_path()

    def has_active_nodeSelector(self):
        return self.get_ValuesYaml().has_active_nodeSelector()

    def has_commentout_nodeSelector(self):
        return self.get_ValuesYaml().has_commentout_nodeSelector()

    def has_expected_structure_for_imagetag(self):
        return self.get_ValuesYaml().has_expected_structure_for_imagetag()

    def correct_commentout_nodeSelector(self):
        return self.get_ValuesYaml().correct_commentout_nodeSelector()

    def specify_nodeSelector_for_rdbox(self):
        return self.get_ValuesYaml().specify_nodeSelector_for_rdbox()

    def specify_storageClass_for_rdbox(self):
        return self.get_ValuesYaml().specify_storageClass_for_rdbox()

    def specify_ingress_for_rdbox(self):
        return self.get_ValuesYaml().specify_ingress_for_rdbox()

    def is_contain_deprecate_string_at_head(self):
        return self.get_ReadmeMd().is_contain_deprecate_string_at_head()

    def is_contain_tldr_string(self):
        return self.get_ReadmeMd().is_contain_tldr_string()

    def is_contain_bitnami_string(self):
        return self.get_ReadmeMd().is_contain_bitnami_string()

    def get_install_command(self):
        return self.get_ReadmeMd().get_install_command()

    def extract_set_options_from_install_command(self):
        return self.get_ReadmeMd().extract_set_options_from_install_command()

    def customize_chartyaml_for_rdbox(self, dir_to_save_icon):
        return self.get_ChartYaml().customize_chartyaml_for_rdbox(dir_to_save_icon)


class ChartYaml(object):
    def __init__(self, module_dir_path, module_name):
        self.module_name = module_name
        self.full_path = os.path.join(module_dir_path, 'Chart.yaml')

    def customize_chartyaml_for_rdbox(self, dir_to_save_icon):
        file_text = ''
        with open(self.full_path) as file:
            obj_values = yaml.safe_load(file)
        try:
            obj_values['maintainers'] = [{'name': 'RDBOX Project', 'email': 'info-rdbox@intec.co.jp'}]
            # collect icon image and change the url to RDBOX #
            url = obj_values.get('icon', None)
            if url is not None:
                original_file_name = url.split('/')[-1]
                _, original_file_ext = os.path.splitext(original_file_name)
                icon_filename = self.module_name + original_file_ext
                try:
                    urllib.request.urlretrieve(url, os.path.join(dir_to_save_icon, icon_filename))
                    obj_values['icon'] = 'https://raw.githubusercontent.com/rdbox-intec/rdbox_app_market/master/icons/' + icon_filename
                except Exception:
                    pass
            ##################################################
            file_text = yaml.dump(obj_values)
        except Exception:
            import traceback
            r_logger.warning(traceback.format_exc())
        with open(self.full_path, 'w') as file:
            file.write(file_text)


class ReadmeMd(object):
    def __init__(self, module_dir_path, module_name):
        self.module_name = module_name
        self.full_path = os.path.join(module_dir_path, 'README.md')

    def is_contain_deprecate_string_at_head(self):
        try:
            with open(self.full_path) as file:
                try:
                    l_XXX_i = [i for i, line in enumerate(file.readlines()) if 'eprecat' in line or 'EPRECAT' in line]
                    if len(l_XXX_i) > 0:
                        if l_XXX_i[0] < 10:
                            return True
                    return False
                except Exception:
                    import traceback
                    r_logger.warning(traceback.format_exc())
        except FileNotFoundError:
            return False

    def is_contain_tldr_string(self):
        return self.is_contain_word_string('TL;DR')

    def is_contain_bitnami_string(self):
        return self.is_contain_word_string('bitnami')

    def is_contain_word_string(self, word):
        try:
            with open(self.full_path) as file:
                try:
                    l_XXX_i = [i for i, line in enumerate(file.readlines()) if word in line]
                    if len(l_XXX_i) > 0:
                        return True
                    return False
                except Exception:
                    import traceback
                    r_logger.warning(traceback.format_exc())
        except FileNotFoundError:
            return False

    def get_install_command(self):
        try:
            file_text = ""
            flg_find_nodeSelector = False
            with open(self.full_path) as file:
                try:
                    for index, line in enumerate(file.readlines()):
                        if re.match(r'^#*\sTL;DR', line):
                            flg_find_nodeSelector = True
                        else:
                            if flg_find_nodeSelector:
                                if re.match(r'^##', line):
                                    break
                                else:
                                    file_text += line
                    latest_helm_install_command = [line for line in file_text.split('\n') if 'helm install' in line]
                    if len(latest_helm_install_command) > 0:
                        latest_helm_install_command = [line for line in file_text.split('\n') if 'helm install' in line][-1]
                    else:
                        latest_helm_install_command = ''
                    latest_helm_install_command = latest_helm_install_command.replace('$ ', '').strip()
                    return latest_helm_install_command
                except Exception:
                    import traceback
                    r_logger.warning(traceback.format_exc())
        except FileNotFoundError:
            return ''

    def extract_set_options_from_install_command(self):
        cmd_str = self.get_install_command()
        _list_of_cmd = cmd_str.split(' ')
        l_XXX_i = [i for i, line in enumerate(_list_of_cmd) if '--set' in line]
        if len(l_XXX_i) > 0:
            set_list = []
            for index in l_XXX_i:
                set_list.append(_list_of_cmd[index + 1].split('=')[0])
            return set_list
        else:
            return []


class RequirementsYaml(object):
    def __init__(self, module_dir_path, module_name):
        self.module_dir_path = module_dir_path
        self.module_name = module_name
        self.full_path = os.path.join(module_dir_path, 'requirements.yaml')
        self.lock_path = os.path.join(module_dir_path, 'requirements.lock')
        self._rm_module_list = []
        self._list = []
        if os.path.exists(self.full_path):
            self.parse()
        else:
            self.full_path = None

    def __repr__(self):
        dep_modules = []
        for req_obj in self._list:
            dep_modules.append(req_obj.get_name())
        return "['%s': '%s']" % (self.module_name, ' '.join(dep_modules))

    def parse(self):
        with open(self.full_path) as file:
            try:
                obj = yaml.safe_load(file)
                for item in obj['dependencies']:
                    req_obj = RequirementsYaml.RequirementObject(item['name'], item['version'], item['repository'], item.get('condition', None), item.get('tags', None))
                    self._list.append(req_obj)
            except Exception:
                self._rm_module_list.append(self.module_name)

    def dump(self):
        obj = {'dependencies': []}
        for req_obj in self._list:
            obj['dependencies'].append(req_obj.get_by_dict())
        text = yaml.dump(obj)
        with open(self.full_path, 'w') as file:
            file.write(text)

    def get_rm_module_list(self):
        return self._rm_module_list

    def get_full_path(self):
        return self.full_path

    def get_RequirementObject_list(self):
        return self._list

    def has_module_of_dependencies(self, module_name):
        ret = False
        for req_obj in self._list:
            if req_obj.name == module_name:
                ret = True
                break
        return ret

    def specify_repository_for_rdbox(self, github):
        parent_url = github.get_url_of_pages()
        for req_obj in self._list:
            req_obj.set_repository(parent_url)

    def remove_lock_file(self):
        try:
            os.remove(self.lock_path)
        except FileNotFoundError:
            pass

    def setup_charts_dir(self):
        parent_dir_path = str(Path(self.module_dir_path).parent)
        charts_dir_path = os.path.join(self.module_dir_path, 'charts')
        os.makedirs(charts_dir_path, exist_ok=True)
        for req_obj in self._list:
            src_path = os.path.join(parent_dir_path, req_obj.get_name())
            dst_path = os.path.join(charts_dir_path, req_obj.get_name())
            shutil.copytree(src_path, dst_path)
            r_logger.debug('COPY DEP Chart')
            r_logger.debug(src_path)
            r_logger.debug(dst_path)

    class RequirementObject(object):
        def __init__(self, name, version, repository, condition=None, tags=None):
            self.name = name
            self.version = version
            self.repository = repository
            self.condition = condition
            self.tags = tags

        def __repr__(self):
            return "<RequirementObject '%s' : '%s' : '%s' : '%s' : '%s'>" % (self.name, self.version, self.repository, self.condition, self.tags)

        def get_name(self):
            return self.name

        def get_version(self):
            return self.version

        def get_repository(self):
            return self.repository

        def set_repository(self, url_repo):
            self.repository = url_repo

        def get_condition(self):
            return self.condition

        def get_tags(self):
            return self.tags

        def get_by_dict(self):
            obj = {}
            obj.setdefault('name', self.get_name())
            obj.setdefault('version', self.get_version())
            obj.setdefault('repository', self.get_repository())
            if self.get_condition() is not None:
                obj.setdefault('condition', self.get_condition())
            if self.get_tags() is not None:
                obj.setdefault('tags', self.get_tags())
            return obj
