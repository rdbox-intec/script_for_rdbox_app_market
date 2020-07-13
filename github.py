#!/usr/bin/env python3
import os
import shutil
import yaml
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
    def __init__(self):
        pass

    def work(self):
        repo = GithubRepos('https://github.com/bitnami/charts', 'bitnami')
        chart_in_specific_dir = ChartInSpecificDir(repo)
        collect_result = chart_in_specific_dir.analyze()
        return collect_result


class GithubRepos(object):

    DIR = os.path.join('/tmp', '.original.charts')
    BRANCH = 'master'

    def __init__(self, url, specific_dir_from_top=''):
        self.url = url
        self.specific_dir_from_top = specific_dir_from_top
        self.repo_dir = os.path.join(self.DIR, self.get_account_name(), self.get_repository_name())
        try:
            shutil.rmtree(self.DIR)
        except FileNotFoundError:
            os.makedirs(self.repo_dir, exist_ok=True)
        self.repo = Repo.clone_from(self.url, self.repo_dir, branch=self.BRANCH, depth=1)

    def get_dirpath(self):
        return self.repo_dir

    def get_dirpath_with_prefix(self):
        return os.path.join(self.get_dirpath(), self.get_specific_dir_from_top())

    def get_url(self):
        return self.url

    def get_specific_dir_from_top(self):
        return self.specific_dir_from_top

    def get_account_name(self):
        return self.url.split('/')[3]

    def get_repository_name(self):
        return self.url.split('/')[4]


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
        isolations, dependon = self.excludes_unknown_dependencies()
        ###
        invalid_key_list = isolations.get_invalid_key_list()
        isolations.remove_by_key_list(invalid_key_list)
        dependon.remove_by_depend_modules_list(invalid_key_list)
        ###
        collect_result = ChartInSpecificDir(self.repo)
        collect_result.merge(isolations)
        collect_result.merge(dependon)
        return collect_result

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
        invalid_keys += not_has_key_nodeSelector
        invalid_keys += invalid_imagetag
        invalid_keys += deprecated
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

    def correct_commentout_nodeSelector(self):
        return self.get_ValuesYaml().correct_commentout_nodeSelector()

    def has_expected_structure_for_imagetag(self):
        return self.get_ValuesYaml().has_expected_structure_for_imagetag()

    def is_contain_deprecate_string(self):
        return self.get_ReadmeMd().is_contain_deprecate_string()


class ValuesYaml(object):
    def __init__(self, module_dir_path, module_name):
        self.module_name = module_name
        self.full_path = os.path.join(module_dir_path, 'values.yaml')

    def has_active_nodeSelector(self):
        with open(self.full_path) as file:
            try:
                obj_values_not_has_key_nodeSelector = yaml.safe_load(file)
                if Util.has_key_recursion(obj_values_not_has_key_nodeSelector, 'nodeSelector') is None:
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

    def correct_commentout_nodeSelector(self):
        file_text = ''
        with open(self.full_path) as file:
            try:
                file_text = file.read()
                file_text = file_text.replace('# nodeSelector: ', 'nodeSelector: {} #')
            except Exception as e:
                print(e)
        if file_text != '':
            with open(self.full_path, 'w') as file:
                print("Modify: " + self.module_name)
                file.write(file_text)

    def has_expected_structure_for_imagetag(self):
        with open(self.full_path) as file:
            values_yaml_obj = yaml.safe_load(file)
            values_yaml_obj = Util.has_key_recursion(values_yaml_obj, 'image')
            if values_yaml_obj is not None:
                if ('repository' not in values_yaml_obj) or ('tag' not in values_yaml_obj):
                    return False
                else:
                    return True


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
    collector = Collector()
    collect_result = collector.work()
    print(collect_result)
    print(len(collect_result.get_all_HelmModule_mapped_by_module_name()))
