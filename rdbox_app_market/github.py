#!/usr/bin/env python3
import os
import shutil
import yaml
import re
from git import Repo

from rdbox_app_market.util import Util
from rdbox_app_market.helm import HelmCommand


class ReferenceGithubRepos(object):

    TOP_DIR = os.path.join('/tmp', '.original.charts')
    REPOS_DIR = os.path.join(TOP_DIR, 'src')
    BRANCH = 'master'

    def __init__(self, url, specific_dir_from_top='', check_tldr=True):
        self.url = url
        self.specific_dir_from_top = specific_dir_from_top
        self.repo_dir = os.path.join(self.REPOS_DIR, self.get_account_name(), self.get_repository_name())
        self.check_tldr = check_tldr
        try:
            shutil.rmtree(self.TOP_DIR)
        except FileNotFoundError:
            os.makedirs(self.repo_dir, exist_ok=True)
        self.repo = Repo.clone_from(self.url, self.repo_dir, branch=self.BRANCH, depth=1)

    def get_dirpath(self):
        return self.repo_dir

    def get_dirpath_with_prefix(self):
        if self.specific_dir_from_top == '':
            return self.get_dirpath()
        else:
            return os.path.join(self.get_dirpath(), self.get_specific_dir_from_top())

    def get_url(self):
        return self.url

    def get_specific_dir_from_top(self):
        return self.specific_dir_from_top

    def get_account_name(self):
        return self.url.split('/')[3]

    def get_repository_name(self):
        return self.url.split('/')[4]

    def get_check_tldr(self):
        return self.check_tldr


class RdboxMasterGithubRepos(object):

    TOP_DIR = os.path.join('/tmp', '.original.charts')
    REPOS_DIR = os.path.join(TOP_DIR, 'rdbox', 'master')
    BRANCH = 'master'

    def __init__(self, url, specific_dir_from_top=''):
        self.url = url
        self.specific_dir_from_top = specific_dir_from_top
        self.repo_dir = os.path.join(self.REPOS_DIR)
        try:
            shutil.rmtree(self.repo_dir)
        except FileNotFoundError:
            os.makedirs(self.repo_dir, exist_ok=True)
        self.repo = Repo.clone_from(self.url, self.repo_dir, branch=self.BRANCH, depth=1)

    def get_dirpath(self):
        return self.repo_dir

    def get_dirpath_with_prefix(self):
        if self.specific_dir_from_top == '':
            return self.get_dirpath()
        else:
            return os.path.join(self.get_dirpath(), self.get_specific_dir_from_top())

    def get_url(self):
        return self.url

    def get_specific_dir_from_top(self):
        return self.specific_dir_from_top


class RdboxGhpagesGithubRepos(object):

    TOP_DIR = os.path.join('/tmp', '.original.charts')
    REPOS_DIR = os.path.join(TOP_DIR, 'rdbox', 'gh-pages')
    BRANCH = 'gh-pages'

    def __init__(self, url, specific_dir_from_top=''):
        self.url = url
        self.specific_dir_from_top = specific_dir_from_top
        self.repo_dir = os.path.join(self.REPOS_DIR)
        try:
            shutil.rmtree(self.repo_dir)
        except FileNotFoundError:
            os.makedirs(self.repo_dir, exist_ok=True)
        self.repo = Repo.clone_from(self.url, self.repo_dir, branch=self.BRANCH, depth=1)

    def get_dirpath(self):
        return self.repo_dir

    def get_dirpath_with_prefix(self):
        if self.specific_dir_from_top == '':
            return self.get_dirpath()
        else:
            return os.path.join(self.get_dirpath(), self.get_specific_dir_from_top())

    def get_url(self):
        return self.url

    def get_specific_dir_from_top(self):
        return self.specific_dir_from_top

    def commit(self):
        self.repo.git.add(self.get_dirpath())
        self.repo.index.commit('Automatic execution by robots.')

    def push(self):
        origin = self.repo.remote(name='origin')
        origin.push()


class Collector(object):
    """
    This instance will collect Helm Charts from the specified GitHub repository.
    Also, if the format is not specified, the Chart will be excluded.
    """
    def __init__(self, repo):
        self.repo = repo

    def work(self):
        chart_in_specific_dir = ChartInSpecificDir(self.repo, ChartInSpecificDir.ANNOTATION_OTHERS)
        isolations_collect_result, dependons_collect_result = chart_in_specific_dir.analyze()
        return isolations_collect_result, dependons_collect_result


class Publisher(object):
    """
    The Instance is to arrange the converting and publish of helm chart.
    like a publishing company.
    """
    def __init__(self, isolations_instance_of_ChartInSpecificDir, dependons_instance_of_ChartInSpecificDir):
        self.isolations_instance_of_ChartInSpecificDir = isolations_instance_of_ChartInSpecificDir
        self.dependons_instance_of_ChartInSpecificDir = dependons_instance_of_ChartInSpecificDir

    def work(self):
        rdbox_gh_repo = RdboxGhpagesGithubRepos('git@github.com:rdbox-intec/rdbox_app_market.git', 'rdbox')
        rdbox_master_repo = RdboxMasterGithubRepos('git@github.com:rdbox-intec/rdbox_app_market.git', 'rdbox')
        #
        invalid_key_list = self.isolations_instance_of_ChartInSpecificDir.convert_and_publish(rdbox_gh_repo)
        self.dependons_instance_of_ChartInSpecificDir.remove_by_depend_modules_list(invalid_key_list)
        # self.dependons_instance_of_ChartInSpecificDir.convert()
        return self.isolations_instance_of_ChartInSpecificDir, self.dependons_instance_of_ChartInSpecificDir


class ChartInSpecificDirConverError(Exception):
    pass


class ChartInSpecificDir(object):

    ANNOTATION_OTHERS = 'others'
    ANNOTATION_ISOLATIONS = 'isolations'
    ANNOTATION_DEPENDONS = 'dependons'

    def __init__(self, repo, annotation=ANNOTATION_OTHERS):
        """Constructor

        Args:
            repo (ReferenceGithubRepos): GitHub repositories to reference.
            annotation (str, optional): The classification of the data held by GitHub repositories when it is classified.
        """
        self.repo = repo
        if annotation == ChartInSpecificDir.ANNOTATION_OTHERS or \
            annotation == ChartInSpecificDir.ANNOTATION_ISOLATIONS or \
                annotation == ChartInSpecificDir.ANNOTATION_DEPENDONS:
            self.annotation = annotation
        else:
            print(annotation)
            raise
        self.specific_dirpath = self.repo.get_dirpath_with_prefix()
        self.all_HelmModule_mapped_by_module_name = {}
        self.all_packaged_tgz_path_mapped_by_module_name = {}

    def __repr__(self):
        return str(self.get_all_HelmModule_mapped_by_module_name())

    def get_annotation(self):
        return self.annotation

    def get_specific_dirpath(self):
        return self.specific_dirpath

    def get_all_HelmModule_mapped_by_module_name(self):
        return self.all_HelmModule_mapped_by_module_name

    def get_all_packaged_tgz_path_mapped_by_module_name(self):
        return self.all_packaged_tgz_path_mapped_by_module_name

    def update(self, all_RequirementsYaml_mapped_by_module_name):
        self.all_HelmModule_mapped_by_module_name.update(all_RequirementsYaml_mapped_by_module_name)
        return self

    def merge(self, instance_of_ChartInSpecificDir):
        self.all_HelmModule_mapped_by_module_name.update(instance_of_ChartInSpecificDir.get_all_HelmModule_mapped_by_module_name())
        return self

    def analyze(self):
        self.all_HelmModule_mapped_by_module_name = self._get_HelmModule_all()
        isolations_collect_result, dependons_collect_result = self.excludes_unknown_dependencies()
        ###
        invalid_key_list = isolations_collect_result.get_invalid_key_list()
        isolations_collect_result.remove_by_key_list(invalid_key_list)
        dependons_collect_result.remove_by_depend_modules_list(invalid_key_list)
        invalid_key_list = dependons_collect_result.get_invalid_key_list()
        dependons_collect_result.remove_by_key_list(invalid_key_list)
        ###
        return isolations_collect_result, dependons_collect_result

    def convert_and_publish(self, repo_for_rdbox):
        invalid_key_list = []
        for module_name, helm_module in self.get_all_HelmModule_mapped_by_module_name().items():
            # ToDo
            # ----- Filter ---------
            if 'bitnami' in self.repo.get_url() and module_name == 'common':
                continue
            # ----------------------
            try:
                if self.get_annotation() == ChartInSpecificDir.ANNOTATION_ISOLATIONS:
                    self._convert_isolations(repo_for_rdbox, module_name, helm_module)
                elif self.get_annotation() == ChartInSpecificDir.ANNOTATION_DEPENDONS:
                    self._convert_dependons(repo_for_rdbox, module_name, helm_module)
            except ChartInSpecificDirConverError:
                invalid_key_list.append(module_name)
            except Exception as e:
                print(e)
                invalid_key_list.append(module_name)
        self.remove_by_key_list(invalid_key_list)
        self._pack(repo_for_rdbox)
        self._publish(repo_for_rdbox)
        return invalid_key_list

    def _pack(self, repo_for_rdbox):
        helm_command = HelmCommand()
        path_of_generation_result = helm_command.repo_index(self.get_specific_dirpath())
        target = os.path.join(repo_for_rdbox.get_dirpath_with_prefix(), os.path.basename(path_of_generation_result))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.move(path_of_generation_result, target)
        for module_name, path in self.get_all_packaged_tgz_path_mapped_by_module_name().items():
            target = os.path.join(repo_for_rdbox.get_dirpath_with_prefix(), os.path.basename(path))
            shutil.move(path, target)
        repo_for_rdbox.commit()

    def _publish(self, repo_for_rdbox):
        repo_for_rdbox.push()

    def _convert_isolations(self, repo_for_rdbox, module_name, helm_module):
        helm_command = HelmCommand()
        helm_module.specify_nodeSelector_for_rdbox()
        helm_module.change_for_rdbox()
        manifest_map = helm_command.template(self.get_specific_dirpath(), module_name, helm_module.extract_set_options_from_install_command())
        if not self._verify_manifest_map(manifest_map):
            ChartInSpecificDirConverError()
        path_of_generation_result = helm_command.package(self.get_specific_dirpath(), module_name, self.get_specific_dirpath())
        if path_of_generation_result != '':
            self.all_packaged_tgz_path_mapped_by_module_name.setdefault(module_name, path_of_generation_result)
        else:
            ChartInSpecificDirConverError()

    def _convert_dependons(self, repo_for_rdbox, module_name, helm_module):
        pass

    def _verify_manifest_map(self, manifest_map):
        flg = True
        for filename, manifest in manifest_map.items():
            if manifest.get('kind') in ['Pod', 'Deployment', 'Job', 'DaemonSet', 'ReplicaSet', 'StatefulSet']:
                node_selector = Util.has_key_recursion(manifest, 'nodeSelector')
                if node_selector is None:
                    if 'test' in filename:
                        flg = True
                    else:
                        flg = False
                        print(manifest)
                        break
                else:
                    flg = True
            else:
                continue
        return flg

    def remove_by_key_list(self, key_list):
        for key in list(set(key_list)):
            print('Delete: ' + key)
            self.all_HelmModule_mapped_by_module_name.pop(key)

    def remove_by_depend_modules_list(self, depend_modules_list):
        del_keys = []
        for depend_module_name in depend_modules_list:
            for module_name, helm_module in self.get_all_HelmModule_mapped_by_module_name().items():
                if helm_module.has_module_of_dependencies(depend_module_name):
                    del_keys.append(module_name)
        for key in list(set(del_keys)):
            print('Delete: ' + key)
            self.all_HelmModule_mapped_by_module_name.pop(key)

    def excludes_unknown_dependencies(self):
        isolations = {}
        dependons = {}
        for module_name, helm_module in self.get_all_HelmModule_mapped_by_module_name().items():
            if helm_module.get_full_path_to_requirements_yaml() is None:
                isolations.setdefault(module_name, helm_module)
            else:
                dependons.setdefault(module_name, helm_module)
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
            print('Delete: ' + key)
            dependons.pop(key)
        return (ChartInSpecificDir(self.repo, ChartInSpecificDir.ANNOTATION_ISOLATIONS).update(isolations),
                ChartInSpecificDir(self.repo, ChartInSpecificDir.ANNOTATION_DEPENDONS).update(dependons))

    def get_invalid_key_list(self):
        invalid_keys = []
        not_has_key_nodeSelector = self._filter_nodeselector()
        invalid_imagetag = self._filter_valuesyaml_imagetag()
        deprecated = self._filter_deprecate()
        if self.repo.get_check_tldr():
            tldr = self._filter_tldr()
        invalid_keys += not_has_key_nodeSelector
        invalid_keys += invalid_imagetag
        invalid_keys += deprecated
        if self.repo.get_check_tldr():
            invalid_keys += tldr
        return list(set(invalid_keys))

    def _filter_nodeselector(self):
        values_not_has_key_nodeSelector = {}
        for module_name, helm_module in self.get_all_HelmModule_mapped_by_module_name().items():
            if helm_module.has_active_nodeSelector() is False:
                values_not_has_key_nodeSelector.setdefault(module_name, helm_module)
        del_keys_values_not_has_key_nodeSelector = []
        for module_name, helm_module in values_not_has_key_nodeSelector.items():
            if helm_module.has_commentout_nodeSelector() is True:
                del_keys_values_not_has_key_nodeSelector.append(module_name)
                helm_module.correct_commentout_nodeSelector()
        for del_key in del_keys_values_not_has_key_nodeSelector:
            values_not_has_key_nodeSelector.pop(del_key)
        # Special support for bitnami.
        if 'bitnami' in self.repo.get_url():
            try:
                values_not_has_key_nodeSelector.pop('common')
            except ValueError:
                pass
            except KeyError:
                pass
        return list(set(values_not_has_key_nodeSelector.keys()))

    def _filter_valuesyaml_imagetag(self):
        invalid_module = []
        for module_name, helm_module in self.get_all_HelmModule_mapped_by_module_name().items():
            if helm_module.has_expected_structure_for_imagetag() is False:
                invalid_module.append(module_name)
        return list(set(invalid_module))

    def _filter_deprecate(self):
        invalid_module = []
        for module_name, helm_module in self.get_all_HelmModule_mapped_by_module_name().items():
            if helm_module.is_contain_deprecate_string():
                invalid_module.append(module_name)
        return list(set(invalid_module))

    def _filter_tldr(self):
        invalid_module = []
        for module_name, helm_module in self.get_all_HelmModule_mapped_by_module_name().items():
            if helm_module.is_contain_tldr_string() is False:
                invalid_module.append(module_name)
        return list(set(invalid_module))

    def _get_HelmModule_all(self):
        module_mapping_data = {}
        specific_dir_path = self.repo.get_dirpath_with_prefix()
        _module_list = self._get_module_list()
        for module_name in _module_list:
            helm_module = HelmModule(specific_dir_path, module_name)
            module_mapping_data.setdefault(module_name, helm_module)
        return module_mapping_data

    def _get_module_list(self):
        stable_module_path = self.repo.get_dirpath_with_prefix()
        li = os.listdir(stable_module_path)
        return li


class HelmModule(object):
    def __init__(self, specific_dir_path, module_name):
        self.module_name = module_name
        self.specific_dir_path = specific_dir_path
        self.module_dir_path = os.path.join(specific_dir_path, module_name)
        # Original Object
        self.requirements_yaml = RequirementsYaml(self.module_dir_path, module_name)
        self.values_yaml = ValuesYaml(self.module_dir_path, module_name)
        self.readme_md = ReadmeMd(self.module_dir_path, module_name)
        self.chart_yaml = ChartYaml(self.module_dir_path, module_name)

    def __repr__(self):
        return str(self.requirements_yaml)

    def get_module_name(self):
        return self.module_name

    def get_RequirementsYaml(self):
        return self.requirements_yaml

    def get_ValuesYaml(self):
        return self.values_yaml

    def get_ReadmeMd(self):
        return self.readme_md

    def get_ChartYaml(self):
        return self.chart_yaml

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

    def is_contain_deprecate_string(self):
        return self.get_ReadmeMd().is_contain_deprecate_string()

    def is_contain_tldr_string(self):
        return self.get_ReadmeMd().is_contain_tldr_string()

    def get_install_command(self):
        return self.get_ReadmeMd().get_install_command()

    def extract_set_options_from_install_command(self):
        return self.get_ReadmeMd().extract_set_options_from_install_command()

    def change_for_rdbox(self):
        return self.get_ChartYaml().change_for_rdbox()


class ChartYaml(object):
    def __init__(self, module_dir_path, module_name):
        self.module_name = module_name
        self.full_path = os.path.join(module_dir_path, 'Chart.yaml')

    def change_for_rdbox(self):
        file_text = ''
        with open(self.full_path) as file:
            try:
                obj_values = yaml.safe_load(file)
                obj_values['maintainers'] = [{'name': 'RDBOX Project', 'email': 'info-rdbox@intec.co.jp'}]
                file_text = yaml.dump(obj_values)
            except Exception as e:
                print(e)
        with open(self.full_path, 'w') as file:
            print("Chart.yaml: " + self.module_name)
            file.write(file_text)


class ValuesYaml(object):
    def __init__(self, module_dir_path, module_name):
        self.module_name = module_name
        self.full_path = os.path.join(module_dir_path, 'values.yaml')

    def has_active_nodeSelector(self):
        with open(self.full_path) as file:
            try:
                obj_values = yaml.safe_load(file)
                if Util.has_key_recursion(obj_values, 'nodeSelector') is None:
                    return False
                else:
                    return True
            except Exception as e:
                print(e)

    def has_commentout_nodeSelector(self):
        with open(self.full_path) as file:
            try:
                l_XXX_i = [i for i, line in enumerate(file.readlines()) if '# nodeSelector: ' in line]
                if len(l_XXX_i) > 0:
                    return True
                else:
                    return False
            except Exception as e:
                print(e)

    def has_expected_structure_for_imagetag(self):
        with open(self.full_path) as file:
            values_yaml_obj = yaml.safe_load(file)
            values_yaml_obj = Util.has_key_recursion(values_yaml_obj, 'image')
            if values_yaml_obj is not None:
                if ('repository' not in values_yaml_obj) or ('tag' not in values_yaml_obj):
                    return False
                else:
                    return True

    def correct_commentout_nodeSelector(self):
        file_text = ''
        with open(self.full_path) as file:
            try:
                file_text = file.read()
                file_text = file_text.replace('# nodeSelector: ', 'nodeSelector: {} #')
            except Exception as e:
                print(e)
        with open(self.full_path, 'w') as file:
            print("Modify: " + self.module_name)
            file.write(file_text)

    def specify_nodeSelector_for_rdbox(self):
        file_text = ""
        nodeselector_text = ""
        with open(self.full_path) as file:
            try:
                obj_values = yaml.safe_load(file)
                obj_nodeselector = Util.has_key_recursion(obj_values, 'nodeSelector')
                if obj_nodeselector is not None:
                    obj_nodeselector.setdefault('beta.kubernetes.io/arch', 'amd64')
                    obj_nodeselector.setdefault('beta.kubernetes.io/os', 'linux')
                obj_nodeselector = {'nodeSelector': obj_nodeselector}
                nodeselector_text = yaml.dump(obj_nodeselector)
                file.seek(0)
                flg_find_nodeSelector = False
                indet_nodeSelector = 0
                for index, line in enumerate(file.readlines()):
                    if re.match(r'^\s*nodeSelector:', line):
                        indet_nodeSelector = len(line.split('nodeSelector')[0])
                        flg_find_nodeSelector = True
                    else:
                        if flg_find_nodeSelector:
                            if line == '\n' or re.match(r'^\s*[0-9a-zA-Z]*:', line) or re.match(r'^\s*#', line):
                                for text in nodeselector_text.split('\n'):
                                    if text != '':
                                        file_text = file_text + ' ' * indet_nodeSelector + text + '\n'
                                file_text = file_text + line
                                flg_find_nodeSelector = False
                            else:
                                continue
                        else:
                            file_text += line
            except Exception as e:
                print(e)
        with open(self.full_path, 'w') as file:
            print("values.yaml: " + self.module_name)
            file.write(file_text)


class ReadmeMd(object):
    def __init__(self, module_dir_path, module_name):
        self.module_name = module_name
        self.full_path = os.path.join(module_dir_path, 'README.md')

    def is_contain_deprecate_string(self):
        try:
            with open(self.full_path) as file:
                try:
                    l_XXX_i = [i for i, line in enumerate(file.readlines()) if 'eprecat' in line]
                    if len(l_XXX_i) > 0:
                        if l_XXX_i[0] < 7:
                            return True
                    return False
                except Exception as e:
                    print(e)
        except FileNotFoundError:
            return False

    def is_contain_tldr_string(self):
        try:
            with open(self.full_path) as file:
                try:
                    l_XXX_i = [i for i, line in enumerate(file.readlines()) if 'TL;DR;' in line]
                    if len(l_XXX_i) > 0:
                        return True
                    return False
                except Exception as e:
                    print(e)
        except FileNotFoundError:
            return False

    def get_install_command(self):
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
                latest_helm_install_command = [line for line in file_text.split('\n') if 'helm install' in line][-1]
                latest_helm_install_command = latest_helm_install_command.replace('$ ', '').strip()
                return latest_helm_install_command
            except Exception as e:
                print(e)

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


class Templates(object):
    def __init__(self, module_dir_path, module_name):
        self.module_name = module_name
        self.templates_dir_path = os.path.join(module_dir_path, 'templates')


class RequirementsYaml(object):
    def __init__(self, module_dir_path, module_name):
        self.module_name = module_name
        self.full_path = os.path.join(module_dir_path, 'requirements.yaml')
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
                    req_obj = RequirementObject(item['name'], item['version'], item['repository'], item.get('condition', ''), item.get('tags', ''))
                    self._list.append(req_obj)
            except Exception:
                self._rm_module_list.append(self.module_name)

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


class RequirementObject(object):
    def __init__(self, name, version, repository, condition, tags):
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

    def get_condition(self):
        return self.condition

    def get_tags(self):
        return self.tags
