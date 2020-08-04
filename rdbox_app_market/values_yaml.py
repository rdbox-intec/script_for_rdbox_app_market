#!/usr/bin/env python3
import os
import requests
import yaml
import re

from rdbox_app_market.util import Util


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
        try:
            with open(self.full_path) as file:
                values_yaml_obj = yaml.safe_load(file)
                values_yaml_obj = Util.has_key_recursion(values_yaml_obj, 'image')
                if values_yaml_obj is not None:
                    if ('repository' in values_yaml_obj or 'name' in values_yaml_obj) and ('tag' in values_yaml_obj):
                        return True
                    else:
                        return False
        except Exception:
            return False

    def correct_commentout_nodeSelector(self):
        file_text = ''
        with open(self.full_path) as file:
            try:
                file_text = file.read()
                file_text = file_text.replace('# nodeSelector: ', 'nodeSelector: {} #')
            except Exception as e:
                print(e)
        with open(self.full_path, 'w') as file:
            print("Modify(nodeSelector): " + self.module_name)
            file.write(file_text)

    def specify_nodeSelector_for_rdbox(self):
        file_text = ""
        lines = []
        with open(self.full_path) as file:
            lines = file.readlines()
        multi_arch_dict = self._get_multi_arch_dict(lines)
        indent_list, indent_unit = self._get_indent_info(lines)
        structure = Structure(indent_unit)
        fileter_of_nodeSelector = FilterOfNodeSelector(indent_unit)
        for i, line in enumerate(lines):
            now_indent = indent_list[i]
            now_struct_str = structure.update(line, now_indent)
            if fileter_of_nodeSelector.is_processing():
                print(now_struct_str)
                is_multi_arch = now_struct_str in multi_arch_dict
                file_text += fileter_of_nodeSelector.filter(line, now_indent, is_multi_arch)
            else:
                file_text += fileter_of_nodeSelector.filter(line, now_indent)
        with open(self.full_path, 'w') as file:
            file.write(file_text)
        return multi_arch_dict

    def _get_multi_arch_dict(self, lines):
        multi_arch_dict = {}
        obj_values = yaml.safe_load('\n'.join(lines))
        node_selector_list = [i for i, line in enumerate(lines) if re.match(r'^\s*nodeSelector:', line)]
        image_list = [i for i, line in enumerate(lines) if re.match(r'^\s*image:', line)]
        if len(node_selector_list) == len(image_list):
            all_image_list = Util.has_key_recursion_full(obj_values, 'image')
            for struct, image_dict in all_image_list.items():
                repo_uri = image_dict.get('repository', image_dict.get('name', ''))
                if self._is_hosted_on_dockerhub(repo_uri):
                    url = self._build_url_of_dockerhub(image_dict, repo_uri)
                    if self._has_multiarch_image(url):
                        multi_arch_dict.setdefault(struct, repo_uri)
        return multi_arch_dict

    def _is_hosted_on_dockerhub(self, repo_url):
        repo_url_list = repo_url.split('/')
        if len(repo_url_list) <= 2:
            return True
        else:
            return False

    def _build_url_of_dockerhub(self, image_tag_dict, repo_uri):
        uri = repo_uri
        repo_url_list = repo_uri.split('/')
        if len(repo_url_list) == 1:
            uri = 'library' + '/' + repo_uri
        url = 'https://hub.docker.com/v2/repositories/{uri}/tags/{tag}'.format(uri=uri, tag=image_tag_dict.get('tag'))
        return url

    def _has_multiarch_image(self, url):
        has_arch_arm = False
        r = requests.get(url)
        if r.status_code == requests.codes.ok:
            data = r.json()
            for v in data.get('images', []):
                if v.get('architecture').startswith('arm'):
                    has_arch_arm = True
        return has_arch_arm

    def _get_indent_info(self, lines):
        il = IndentList()
        for line in lines:
            il.add_with_line_of_text(line)
        return il.to_list(), il.get_unit_indent_length()


class FilterOfNodeSelector(object):
    def __init__(self, indent_unit):
        self.indent_unit = indent_unit
        self.node_selector_indent = 0
        self.is_ns_in_processing = False
        self.original_nodeSelector_text = ''

    def filter(self, line, indent, is_multi_arch=False):
        if not self.is_ns_in_processing:
            if self._is_start_of_block_element(line, indent):
                return ''
            else:
                return line
        else:
            return self._processing_of_block_elements(line, is_multi_arch)

    def is_processing(self):
        return self.is_ns_in_processing

    def _is_start_of_block_element(self, line, indent):
        if re.match(r'^\s*nodeSelector:', line):
            self.is_ns_in_processing = True
            self.original_nodeSelector_text += line
            self.node_selector_indent = indent
            return True
        return False

    def _processing_of_block_elements(self, line, is_multi_arch=False):
        file_text = ''
        if line == '\n' or re.match(r'^\s*[0-9a-zA-Z]*:', line) or re.match(r'^\s*#', line):
            print(self.original_nodeSelector_text)
            ns_obj = yaml.safe_load(self.original_nodeSelector_text)
            if not isinstance(ns_obj.get('nodeSelector'), dict):
                ns_obj = {'nodeSelector': {}}
            ns_obj.get('nodeSelector').setdefault('beta.kubernetes.io/os', 'linux')
            if not is_multi_arch:
                ns_obj.get('nodeSelector').setdefault('beta.kubernetes.io/arch', 'amd64')
            aligned_nodeSelector_text = yaml.dump(ns_obj, indent=self.indent_unit)
            for text in aligned_nodeSelector_text.split('\n'):
                file_text = file_text + ' ' * self.node_selector_indent + text + '\n'
            self._reset()
        else:
            self.original_nodeSelector_text += line
        return file_text

    def _reset(self):
        self.is_ns_in_processing = False
        self.original_nodeSelector_text = ''


class Structure(object):
    def __init__(self, indent_unit):
        self.struct = ['_']
        self.indent_unit = indent_unit
        self.prev_indent = 0
        self.prev_line_without_comment = ''

    def update(self, line, now_indent):
        if now_indent >= 0:
            if now_indent > self.prev_indent:
                if self.prev_line_without_comment.strip().endswith(':'):
                    self.struct.append(self.prev_line_without_comment.strip().rstrip(':'))
            if now_indent < self.prev_indent:
                _unit = (self.prev_indent - now_indent) / self.indent_unit
                if _unit.is_integer():
                    for i in range(int(_unit)):
                        if len(self.struct) > 1:
                            self.struct.pop()
            self.prev_line_without_comment = line
            self.prev_indent = now_indent
        return self.to_str()

    def to_str(self, sep='.'):
        return sep.join(self.struct)


class IndentList(object):
    def __init__(self):
        self.result_indent_list = []
        # Filter #
        self.filters = []
        self.filters.append(FilterOfBlockElementForIndentList(r'^\s*[0-9a-zA-Z\-]{1,}: (\>|\|)(\-|\+|)'))  # Multi Line Element
        self.filters.append(FilterOfBlockElementForIndentList(r'^\s*-'))                                   # List Element

    def append(self, indent):
        self.result_indent_list.append(indent)

    def to_list(self):
        return self.result_indent_list

    def add_with_line_of_text(self, line):
        # Validation #
        if re.match(r'^\s*#', line) or re.match(r'^\s*\n', line):
            self.append(-1)
            return
        # RAW Indent #
        indent_length_of_processing_line = self._get_indent_length_of_target(line)
        # Filter #
        for filter in self.filters:
            if filter.is_filterd(line, indent_length_of_processing_line):
                self.append(-1)
                return
        self.append(indent_length_of_processing_line)

    def get_unit_indent_length(self):
        unit = 0
        for indent in self.result_indent_list:
            if indent == -1:
                continue
            if indent > 0:
                unit = indent
                break
        return unit

    def _get_indent_length_of_target(self, line):
        indent_length = 0
        head_str = re.split(r'[0-9a-zA-Z\-\"\']{1,}', line)
        if head_str[0].startswith(' '):
            indent_length = len(head_str[0])
        else:
            indent_length = 0
        return indent_length


class FilterOfBlockElementForIndentList(object):
    def __init__(self, regex):
        self.regex = regex
        self.is_block_of_yaml_in_processing = False
        self.indent_length_of_block_of_yaml = -1

    def is_filterd(self, line, indent_length_of_processing_line):
        if not self.is_block_of_yaml_in_processing:
            if self._is_start_of_block_element(line, indent_length_of_processing_line):
                return True
        return self._processing_of_block_elements(indent_length_of_processing_line)

    def _is_start_of_block_element(self, line, indent_length_of_processing_line):
        if re.match(self.regex, line):
            self.is_block_of_yaml_in_processing = True
            if self.indent_length_of_block_of_yaml == -1:
                self.indent_length_of_block_of_yaml = indent_length_of_processing_line
            return True
        return False

    def _processing_of_block_elements(self, indent_length_of_processing_line):
        if self.is_block_of_yaml_in_processing and indent_length_of_processing_line >= 0:
            if indent_length_of_processing_line > self.indent_length_of_block_of_yaml:
                # countinue
                return True
            else:
                # end
                self._reset()
                return False
        return False

    def _reset(self):
        self.is_block_of_yaml_in_processing = False
        self.indent_length_of_list_of_yaml = -1
