#!/usr/bin/env python3
import os
import shutil
import yaml
from git import Repo


class Collector(object):
    def __init__(self):
        pass

    def work(self):
        repo = GithubRepos('https://github.com/bitnami/charts', 'bitnami')
        chart_in_specific_dir = ChartInSpecificDir(repo)
        isolations, dependon = chart_in_specific_dir.analyze().excludes_unknown_dependencies()
        invalid_key_list = isolations.get_invalid_key_list()
        ####
        isolations.remove_by_key_list(invalid_key_list)
        dependon.remove_by_depend_modules_list(invalid_key_list)
        collect_result = ChartInSpecificDir(repo)
        collect_result.merge(isolations)
        collect_result.merge(dependon)
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
        self.all_RequirementsYaml_mapped_by_module_name = {}

    def __repr__(self):
        return str(self.all_RequirementsYaml_mapped_by_module_name)

    def merge(self, instance_of_GithubRepos):
        self.all_RequirementsYaml_mapped_by_module_name.update(
            instance_of_GithubRepos.get_all_RequirementsYaml_mapped_by_module_name())
        return self

    def update(self, all_RequirementsYaml_mapped_by_module_name):
        self.all_RequirementsYaml_mapped_by_module_name.update(all_RequirementsYaml_mapped_by_module_name)
        return self

    def analyze(self):
        self.all_RequirementsYaml_mapped_by_module_name = self._get_RequirementsYaml_all()
        return self

    def excludes_unknown_dependencies(self):
        isolations = {}
        dependon = {}
        for module_name, req_yaml in self.all_RequirementsYaml_mapped_by_module_name.items():
            if req_yaml.get_full_path() is None:
                isolations.setdefault(module_name, req_yaml)
            else:
                dependon.setdefault(module_name, req_yaml)
        candidate = []
        for module_name, req_yaml in dependon.items():
            for req_obj in req_yaml.get_RequirementObjectList():
                candidate.append(req_obj.name)
        candidate = list(set(candidate))
        del_keys = []
        for candidate_module_name in candidate:
            if candidate_module_name not in isolations:
                if candidate_module_name not in dependon:
                    for module_name, req_yaml in dependon.items():
                        if req_yaml.has_module_of_dependencies(candidate_module_name):
                            del_keys.append(module_name)
        for key in list(set(del_keys)):
            print('Delete: ' + key)
            dependon.pop(key)
        return ChartInSpecificDir(self.repo).update(isolations), ChartInSpecificDir(self.repo).update(dependon)

    def get_all_RequirementsYaml_mapped_by_module_name(self):
        return self.all_RequirementsYaml_mapped_by_module_name

    def get_specific_dirpath(self):
        return self.specific_dirpath

    def get_invalid_key_list(self):
        invalid_keys = []
        not_has_key_nodeSelector = self.filter_nodeselector()
        invalid_imagetag = self.filter_valuesyaml_imagetag()
        deprecated = self.filter_deprecate()
        invalid_keys += not_has_key_nodeSelector
        invalid_keys += invalid_imagetag
        invalid_keys += deprecated
        return list(set(invalid_keys))

    def filter_nodeselector(self):
        values_not_has_key_nodeSelector = []
        for module_name, req_yaml in self.all_RequirementsYaml_mapped_by_module_name.items():
            values_yaml_path = os.path.join(self.specific_dirpath, module_name, 'values.yaml')
            with open(values_yaml_path) as file:
                try:
                    obj_values_not_has_key_nodeSelector = yaml.safe_load(file)
                    if self._has_key_recursion(obj_values_not_has_key_nodeSelector, 'nodeSelector') is None:
                        values_not_has_key_nodeSelector.append(module_name)
                except Exception as e:
                    print(e)
        for module_name in values_not_has_key_nodeSelector:
            file_text = ''
            values_yaml_path = os.path.join(self.specific_dirpath, module_name, 'values.yaml')
            with open(values_yaml_path, 'r') as file:
                try:
                    l_XXX_i = [i for i, line in enumerate(file.readlines()) if '# nodeSelector: ' in line]
                    if len(l_XXX_i) > 0:
                        values_not_has_key_nodeSelector.remove(module_name)
                        file.seek(0)
                        file_text = file.read()
                        file_text = file_text.replace('# nodeSelector: ', 'nodeSelector: {} #')
                except Exception as e:
                    print(e)
            if file_text != '':
                with open(values_yaml_path, 'w') as file:
                    print("Modify: " + module_name)
                    file.write(file_text)
        # Special support for bitnami.
        if 'bitnami' in self.repo.get_url():
            try:
                values_not_has_key_nodeSelector.remove('common')
            except ValueError:
                pass
        return list(set(values_not_has_key_nodeSelector))

    def filter_valuesyaml_imagetag(self):
        invalid_module = []
        for module_name, req_yaml in self.all_RequirementsYaml_mapped_by_module_name.items():
            values_yaml_path = os.path.join(self.specific_dirpath, module_name, 'values.yaml')
            with open(values_yaml_path) as file:
                values_yaml_obj = yaml.safe_load(file)
                values_yaml_obj = self._has_key_recursion(values_yaml_obj, 'image')
                if values_yaml_obj is not None:
                    if 'repository' not in values_yaml_obj or 'tag' not in values_yaml_obj:
                        invalid_module.append(module_name)
        return list(set(invalid_module))

    def filter_deprecate(self):
        invalid_module = []
        for module_name, req_yaml in self.all_RequirementsYaml_mapped_by_module_name.items():
            values_yaml_path = os.path.join(self.specific_dirpath, module_name, 'README.md')
            try:
                with open(values_yaml_path) as file:
                    try:
                        l_XXX_i = [i for i, line in enumerate(file.readlines()) if 'eprecat' in line]
                        if len(l_XXX_i) > 0:
                            if l_XXX_i[0] < 7:
                                invalid_module.append(module_name)
                    except Exception as e:
                        print(e)
            except FileNotFoundError:
                pass
        return list(set(invalid_module))

    def remove_by_key_list(self, key_list):
        for key in list(set(key_list)):
            print('Delete: ' + key)
            self.all_RequirementsYaml_mapped_by_module_name.pop(key)

    def remove_by_depend_modules_list(self, depend_modules_list):
        del_keys = []
        for depend_module_name in depend_modules_list:
            for module_name, req_yaml in self.all_RequirementsYaml_mapped_by_module_name.items():
                if req_yaml.has_module_of_dependencies(depend_module_name):
                    del_keys.append(module_name)
        for key in list(set(del_keys)):
            print('Delete: ' + key)
            self.all_RequirementsYaml_mapped_by_module_name.pop(key)

    def _get_RequirementsYaml_all(self):
        module_mapping_data = {}
        stable_module_path = self.repo.get_dirpath_with_prefix()
        _module_list = self._get_module_list()
        for module_name in _module_list:
            req_yaml = RequirementsYaml(stable_module_path, module_name)
            module_mapping_data.setdefault(module_name, req_yaml)
        return module_mapping_data

    def _get_module_list(self):
        stable_module_path = self.repo.get_dirpath_with_prefix()
        li = os.listdir(stable_module_path)
        return li

    def _has_key_recursion(self, obj, key):
        if key in obj:
            return obj[key]
        for k, v in obj.items():
            if isinstance(v, dict):
                item = self._has_key_recursion(v, key)
                if item is not None:
                    return item


class HelmModule(object):
    def __init__(self, module_name, dir_path):
        self.module_name = module_name
        self.dir_path = dir_path


class RequirementsYaml(object):
    def __init__(self, base_path, module_name):
        self.module_name = module_name
        self.base_path = base_path
        self.full_path = os.path.join(base_path, module_name, 'requirements.yaml')
        self._rm_module_list = []
        self._list = []
        if os.path.exists(self.full_path):
            self.parse()
        else:
            self.base_path = None
            self.full_path = None

    def __repr__(self):
        dep_modules = []
        for req_obj in self._list:
            dep_modules.append(req_obj.get_name())
        return "<'%s': '%s'>\n" % (self.module_name, ' '.join(dep_modules))

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

    def get_RequirementObjectList(self):
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
