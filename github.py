#!/usr/bin/env python3
import os
import shutil
import yaml
import re
from git import Repo


class Util(object):
    @classmethod
    def has_key_recursion(cls, obj, key):
        if key in obj:
            return obj[key]
        for k, v in obj.items():
            if isinstance(v, dict):
                item = cls.has_key_recursion(v, key)
                if item is not None:
                    return item


class Collector(object):
    def __init__(self, repo):
        self.repo = repo

    def work(self):
        chart_in_specific_dir = ChartInSpecificDir(self.repo)
        isolations_collect_result, dependons_collect_result = chart_in_specific_dir.analyze()
        return isolations_collect_result, dependons_collect_result


class Converter(object):
    def __init__(self, instance_of_ChartInSpecificDir):
        self.collect_result = instance_of_ChartInSpecificDir

    def work(self):
        self.collect_result.convert()


class GithubRepos(object):

    DIR = os.path.join('/tmp', '.original.charts')
    BRANCH = 'master'

    def __init__(self, url, specific_dir_from_top='', check_tldr=True):
        self.url = url
        self.specific_dir_from_top = specific_dir_from_top
        self.repo_dir = os.path.join(self.DIR, self.get_account_name(), self.get_repository_name())
        self.check_tldr = check_tldr
        try:
            shutil.rmtree(self.DIR)
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


class ChartInSpecificDir(object):
    def __init__(self, repo):
        self.repo = repo
        self.specific_dirpath = self.repo.get_dirpath_with_prefix()
        self.all_HelmModule_mapped_by_module_name = {}

    def __repr__(self):
        return str(self.get_all_HelmModule_mapped_by_module_name())

    def get_specific_dirpath(self):
        return self.specific_dirpath

    def get_all_HelmModule_mapped_by_module_name(self):
        return self.all_HelmModule_mapped_by_module_name

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

    def convert(self):
        for module_name, helm_module in self.get_all_HelmModule_mapped_by_module_name().items():
            if not ('bitnami' in self.repo.get_url() and module_name == 'common'):
                helm_module.specify_nodeSelector_for_rdbox()
                helm_module.change_for_rdbox()
                helm_module.extract_set_options_from_install_command()

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
        dependon = {}
        for module_name, helm_module in self.get_all_HelmModule_mapped_by_module_name().items():
            if helm_module.get_full_path_to_requirements_yaml() is None:
                isolations.setdefault(module_name, helm_module)
            else:
                dependon.setdefault(module_name, helm_module)
        candidate = []
        for module_name, helm_module in dependon.items():
            for req_obj in helm_module.get_RequirementObject_list():
                candidate.append(req_obj.name)
        candidate = list(set(candidate))
        del_keys = []
        for candidate_module_name in candidate:
            if (candidate_module_name not in isolations) and (candidate_module_name not in dependon):
                for module_name, helm_module in dependon.items():
                    if helm_module.has_module_of_dependencies(candidate_module_name):
                        del_keys.append(module_name)
        for key in list(set(del_keys)):
            print('Delete: ' + key)
            dependon.pop(key)
        return ChartInSpecificDir(self.repo).update(isolations), ChartInSpecificDir(self.repo).update(dependon)

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
            print("Specifiy: " + self.module_name)
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
                set_list.append(_list_of_cmd[index + 1])
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


if __name__ == '__main__':
    repo = GithubRepos('https://github.com/bitnami/charts', 'bitnami')
    collector = Collector(repo)
    isolations_collect_result, dependons_collect_result = collector.work()
    print('---')
    converter = Converter(isolations_collect_result)
    converter.work()
    # collect_result = ChartInSpecificDir(repo)
    # collect_result.merge(isolations_collect_result)
    # collect_result.merge(dependons_collect_result)
    # print('---')
    # converter = Converter(collect_result)
    # converter.work()
