#!/usr/bin/env python3
import os
import requests
import yaml
import re
from typing import Dict, List, Tuple
from logging import getLogger

import rdbox_app_market.config
from rdbox_app_market.util import Util

r_logger = getLogger('rdbox_cli')
r_print = getLogger('rdbox_cli').getChild("stdout")


class ValuesYaml(object):
    def __init__(self, module_dir_path: str, module_name: str):
        self.module_name = module_name
        self.full_path = os.path.join(module_dir_path, 'values.yaml')

    def has_active_nodeSelector(self) -> bool:
        try:
            lines = self.readlines()
            obj_values = yaml.safe_load(''.join(lines))
            if Util.has_key_recursion(obj_values, 'nodeSelector') is None:
                return False
            else:
                return True
        except Exception:
            import traceback
            r_logger.warning(traceback.format_exc())
            return False

    def has_commentout_nodeSelector(self) -> bool:
        try:
            lines = self.readlines()
            l_XXX_i = [i for i, line in enumerate(lines) if '# nodeSelector: ' in line]
            if len(l_XXX_i) > 0:
                return True
            else:
                return False
        except Exception:
            import traceback
            r_logger.warning(traceback.format_exc())
            return False

    def correct_commentout_nodeSelector(self):
        try:
            is_changed = False
            file_text = ''.join(self.readlines())
            write_text = file_text.replace('# nodeSelector: ', 'nodeSelector: {} #')
            if file_text != write_text:
                self.write_text(write_text)
                is_changed = True
            return write_text, is_changed
        except Exception as e:
            import traceback
            r_logger.warning(traceback.format_exc())
            raise e

    def has_expected_structure_for_imagetag(self):
        try:
            lines = self.readlines()
            values_yaml_obj = yaml.safe_load(''.join(lines))
            values_yaml_obj = Util.has_key_recursion(values_yaml_obj, 'image')
            if values_yaml_obj is not None:
                if ('repository' in values_yaml_obj or 'name' in values_yaml_obj) and ('tag' in values_yaml_obj):
                    return True
                else:
                    return False
        except Exception:
            import traceback
            r_logger.warning(traceback.format_exc())
            return False

    def specify_nodeSelector_for_rdbox(self):
        file_text = ""
        lines = self.readlines()
        flt = FilterOfNodeSelector(self.module_name, lines)
        file_text, is_changed = flt.filter()
        multi_arch_dict = flt.get_multi_arch_dict(lines)
        if is_changed:
            self.write_text(file_text)
        return file_text, is_changed, multi_arch_dict

    def specify_storageClass_for_rdbox(self):
        file_text = ''
        lines = self.readlines()
        flt = FilterOfStorageClass(self.module_name, lines)
        file_text, is_changed = flt.filter()
        if is_changed:
            self.write_text(file_text)
        return file_text, is_changed

    def specify_ingress_for_rdbox(self):
        file_text = ""
        lines = self.readlines()
        flt = FilterOfIngress(self.module_name, lines)
        lines, is_changed = flt.filter()
        file_text = ''.join(lines)
        if is_changed:
            self.write_text(file_text)
        return file_text, is_changed

    def readlines(self):
        lines = []
        with open(self.full_path) as file:
            lines = file.readlines()
        return lines

    def write_text(self, file_text):
        with open(self.full_path, 'w') as file:
            file.write(file_text)


class FilterOfStorageClass(object):
    def __init__(self, module_name: str, lines: List[str]):
        """Filter of storageClass

        Args:
            module_name (str): module name
            lines (list): A list of values.yaml divided by a new line
        """
        self.module_name = module_name
        self.lines = lines

    def filter(self):
        file_text = ''
        try:
            # Validation #
            if not self.__has_storageClass_tag_with_lines(self.lines):
                return ''.join(self.lines), False
            if self.__has_global_tag_with_lines(self.lines):
                # global setting
                not_find_storageClass_in_global, file_text = self.__edit_storageClass_in_global_tag(self.lines)
                if not_find_storageClass_in_global:
                    # If editing the global tag fails, edit the Separate Setting.
                    file_text = self.__edit_storageClass_of_the_separate(self.lines)
            else:
                # Separate Setting
                file_text = self.__edit_storageClass_of_the_separate(self.lines)
            return file_text, True
        except Exception:
            import traceback
            r_logger.warning(traceback.format_exc())
            return ''.join(self.lines), False

    def __has_global_tag_with_lines(self, lines):
        return self.__has_regex_tag_with_lines(lines, r'^#\sglobal:') or self.__has_regex_tag_with_lines(lines, r'^global:')

    def __has_storageClass_tag_with_lines(self, lines):
        return self.__has_regex_tag_with_lines(lines, r'^\s*#*\s*storageClass:')

    def __edit_storageClass_in_global_tag(self, lines):
        file_text = ''
        not_find_storageClass_in_global = False
        _, indent_unit = self.__get_indent_info(lines)
        is_indent_of_global_tag = False
        raw_global_tag = ''     # ex. global: or # global:
        text_in_global_tag = ''
        for i, line in enumerate(lines):
            if re.match(r'^#\sglobal:', line) or re.match(r'^global:', line):
                raw_global_tag = line
                is_indent_of_global_tag = True
            else:
                if is_indent_of_global_tag:
                    if re.match(r'^\s*#*\s*storageClass:', line):
                        # find in global tag.
                        text_in_global_tag = 'global:\n' + text_in_global_tag
                        storageClass = rdbox_app_market.config.get('kubernetes', 'common_storage')
                        text_in_global_tag += ' ' * indent_unit + 'storageClass: ' + storageClass + '\n'
                        is_indent_of_global_tag = False
                        file_text += text_in_global_tag
                        continue
                    if re.match(r'^\s*\n', line) or re.match(r'^[0-9a-zA-Z]*:', line):
                        # not find in global tag.
                        text_in_global_tag = raw_global_tag + text_in_global_tag + line
                        is_indent_of_global_tag = False
                        file_text += text_in_global_tag
                        not_find_storageClass_in_global = True
                        continue
                    text_in_global_tag += line
                else:
                    file_text += line
        return not_find_storageClass_in_global, file_text

    def __edit_storageClass_of_the_separate(self, lines):
        indent_list, _ = self.__get_indent_info(lines)
        file_text = ''
        for i, line in enumerate(lines):
            if re.match(r'^\s*#*\s*storageClass:\s[\-\_\/\"\'a-zA-Z0-9]+', line):
                indent_of_backward, indent_of_forward = self.__get_indent_of_back_and_forward(indent_list, i)
                storageClass = rdbox_app_market.config.get('kubernetes', 'common_storage')
                if indent_of_backward == indent_of_forward:
                    file_text = file_text + ' ' * indent_of_backward + 'storageClass: ' + storageClass + '\n'
                else:
                    line_indent = re.sub(r'(^\s*)#*(\s*)(storageClass:\s[\[\]\.\_\-\"\'\/a-zA-Z0-9]*\n)', r'\1', line)
                    if len(line_indent) == indent_of_backward or len(line_indent) == indent_of_forward:
                        file_text = file_text + line_indent + 'storageClass: ' + storageClass + '\n'
                    else:
                        file_text += line
            else:
                file_text += line
        return file_text

    def __get_indent_of_back_and_forward(self, indent_list, now_processing_line):
        indent_of_backward = 0
        indent_of_forward = 0
        for i in reversed(range(now_processing_line)):
            if indent_list[i] >= 0:
                indent_of_backward = indent_list[i]
                break
        for i in range(now_processing_line, len(indent_list)):
            if indent_list[i] >= 0:
                indent_of_forward = indent_list[i]
                break
        return indent_of_backward, indent_of_forward

    def __has_regex_tag_with_lines(self, lines, regex):
        result = False
        for line in lines:
            if re.match(regex, line):
                result = True
                break
        return result

    def __get_indent_info(self, lines):
        il = IndentList()
        for line in lines:
            il.add_with_line_of_text(line)
        return il.to_list(), il.get_unit_indent_length()


class FilterOfIngress(object):
    def __init__(self, module_name: str, lines: List[str]):
        """Filter of ingress

        Args:
            module_name (str): module name
            lines (list): A list of values.yaml divided by a new line
        """
        self.module_name = module_name
        self.lines = lines
        self.ingress_dicts = Util.has_key_recursion_full(yaml.safe_load('\n'.join(lines)), 'ingress')

    def filter(self) -> Tuple[List[str], bool]:
        """Edit the ingressTag.

        Returns:
            List[str]: After editing values.yaml
            bool: Changed or not (True means already changed)
        """
        flt: BaseFilterOfIngress
        # Validation
        if len(self.ingress_dicts.keys()) == 0:
            return self.lines, False
        if not self.__has_key_of_hosts_with(self.ingress_dicts):
            return self.lines, False
        # Select
        if self.__has_str_value_of_hosts(self.ingress_dicts):
            # Validation
            if not self.__passed_str_hosts_ingress(self.ingress_dicts):
                return self.lines, False
            flt = FilterOfStrHostsIngress(self.module_name, self.lines, self.ingress_dicts)
        elif self.__has_dict_value_of_hosts(self.ingress_dicts):
            # Validation
            if not self.__passed_dict_hosts_ingress(self.ingress_dicts):
                return self.lines, False
            flt = FilterOfDictHostsIngress(self.module_name, self.lines, self.ingress_dicts)
        else:
            return self.lines, False
        # Execute
        try:
            self.lines = flt.filter()
            return self.lines, True
        except Exception:
            return self.lines, False

    def __has_key_of_hosts_with(self, ingress_dict):
        result = False
        for _, v in ingress_dict.items():
            if 'hosts' in v:
                result = True
            else:
                result = False
                break
        return result

    def __has_dict_value_of_hosts(self, ingress_dict):
        result = False
        for k, v in ingress_dict.items():
            if isinstance(v.get('hosts'), list):
                if len(v.get('hosts')) == 0:
                    result = False
                    break
                else:
                    if isinstance(v.get('hosts')[0], dict):
                        result = True
                    else:
                        result = False
                        break
            else:
                result = False
                break
        return result

    def __has_str_value_of_hosts(self, ingress_dict):
        result = False
        for k, v in ingress_dict.items():
            if isinstance(v.get('hosts'), list):
                if len(v.get('hosts')) == 0:
                    result = True
                else:
                    if isinstance(v.get('hosts')[0], str):
                        result = True
                    else:
                        result = False
                        break
            else:
                if 'hosts' in v:
                    # For None
                    result = True
                else:
                    result = False
                    break
        return result

    def __passed_str_hosts_ingress(self, ingress_dict):
        result = False
        for k, v in ingress_dict.items():
            if 'enabled' not in v:
                result = False
                break
            if 'path' not in v:
                result = False
                break
            if 'annotations' not in v:
                result = False
                break
            if 'tls' not in v:
                result = False
                break
            result = True
        return result

    def __passed_dict_hosts_ingress(self, ingress_dict):
        result = False
        for k, v in ingress_dict.items():
            if 'enabled' not in v:
                result = False
                break
            if 'certManager' not in v:
                result = False
                break
            if 'name' not in v['hosts'][0]:
                result = False
                break
            if 'path' not in v['hosts'][0]:
                result = False
                break
            if 'tls' not in v['hosts'][0]:
                result = False
                break
            if 'tlsSecret' not in v['hosts'][0]:
                result = False
                break
            result = True
        return result


class BaseFilterOfIngress(object):
    def __init__(self, module_name: str, lines: list, ingress_dicts: dict):
        self.module_name = module_name
        self.lines = lines
        self.ingress_dicts = ingress_dicts
        self.indent_unit = 2

    def filter(self) -> List[str]:
        raise Exception

    def generator(self):
        self.__update_lines_info()
        for index, line in enumerate(self.lines):
            now_indent = self.indent_list[index]
            now_struct_str = self.structure.update(line, now_indent)
            if '.ingress' in now_struct_str:
                yield index, line, now_indent, self.structure

    def filter_enabled(self):
        for index, line, now_indent, _ in self.generator():
            if re.match(r'^\s*enabled:', line):
                self.lines[index] = ' ' * now_indent + 'enabled: true' + '\n'

    def filter_annotations(self):
        need_to_uncomment_q = False
        count_uncomment = 0
        indent_uncomment = 0
        for index, line, now_indent, structure in self.generator():
            if need_to_uncomment_q:
                if re.match(r'^\s*#+', line):
                    if re.match(r'^\s*#+\s*[\.\_\-\"\'\/a-zA-Z0-9]+:\s[\.\_\-\"\'\/a-zA-Z0-9]+', line):
                        self.lines[index] = indent_uncomment + re.sub(r'^\s*#+\s*([\.\_\-\"\'\/a-zA-Z0-9]+:\s[\.\_\-\"\'\/a-zA-Z0-9]+)', r'\1', line)
                        count_uncomment += 1
                else:
                    if count_uncomment == 0:
                        self.lines.insert(index, indent_uncomment + 'kubernetes.io/ingress.class: nginx' + '\n')
                        self.lines.insert(index, indent_uncomment + 'kubernetes.io/tls-acme: \'true\'' + '\n')
                        self.__update_lines_info()
                    need_to_uncomment_q = False
                    count_uncomment = 0
            if re.match(r'^\s*#*\s*annotations:', line):
                need_to_uncomment_q = True
                target_line = line
                if now_indent < 0:
                    _indent_unit_from_struct = len(structure.to_str().split('.')) - 1
                    indent_uncomment = ' ' * _indent_unit_from_struct * self.indent_unit + ' ' * self.indent_unit
                    target_line = ' ' * _indent_unit_from_struct * self.indent_unit + 'annotations:' + '\n'
                else:
                    indent_uncomment = ' ' * now_indent + ' ' * self.indent_unit
                annotations_item = self.ingress_dicts.get('.'.join(structure.parent())).get('annotations', None)
                if annotations_item is None:
                    self.lines[index] = target_line
                    continue
                if len(annotations_item) == 0:
                    self.lines[index] = ' ' * now_indent + 'annotations:' + '\n'
                    continue
                elif len(annotations_item) > 0:
                    self.lines[index] = target_line
                    continue
            else:
                continue

    def lines_insert(self, index, content):
        self.lines.insert(index, content)
        self.__update_lines_info()

    def build_hostname(self, structure):
        hostname = '.'.join(structure.get_struct()[1:-1])
        if hostname == '':
            hostname = self.module_name + '.' + rdbox_app_market.config.get('kubernetes', 'common_domain')
        else:
            hostname = hostname + '.' + self.module_name + '.' + rdbox_app_market.config.get('kubernetes', 'common_domain')
        return hostname

    def __get_indent_info(self):
        il = IndentList()
        for line in self.lines:
            il.add_with_line_of_text(line)
        return il.to_list(), il.get_unit_indent_length()

    def __update_lines_info(self):
        self.indent_list, self.indent_unit = self.__get_indent_info()
        self.structure = Structure(self.indent_unit)


class FilterOfDictHostsIngress(BaseFilterOfIngress):
    def __init__(self, module_name: str, lines: list, ingress_dicts: dict):
        super().__init__(module_name, lines, ingress_dicts)

    def filter(self):
        self.filter_enabled()
        self.filter_annotations()
        self.filter_certManager()
        self.filter_name()
        self.filter_tls()
        self.filter_tlsSecret()
        self.filter_tlsHosts()
        return self.lines

    def filter_certManager(self):
        for index, line, now_indent, _ in self.generator():
            if re.match(r'^\s*certManager:', line):
                self.lines[index] = ' ' * now_indent + 'certManager: true' + '\n'

    # section of .ingress.hosts
    def filter_name(self):
        for index, line, _, structure in self.generator():
            if re.match(r'^\s*-*\s*name:', line):
                hostname = self.build_hostname(structure)
                self.lines[index] = re.sub(r'(^\s*-*\s*)(name:\s[\.\_\-\"\'\/a-zA-Z0-9]*\n)', r'\1', line) + 'name: ' + hostname + '\n'

    def filter_tls(self):
        for index, line, _, _ in self.generator():
            if re.match(r'^\s*-*\s*tls:', line):
                self.lines[index] = re.sub(r'(^\s*-*\s*)(tls:\s[\.\_\-\"\'\/a-zA-Z0-9]*\n)', r'\1', line) + 'tls: true' + '\n'

    def filter_tlsSecret(self):
        for index, line, _, _ in self.generator():
            if re.match(r'^\s*-*\s*tlsSecret:', line):
                self.lines[index] = re.sub(r'(^\s*-*\s*)(tlsSecret:\s[\.\_\-\"\'\/a-zA-Z0-9]*\n)', r'\1', line) + 'tlsSecret: ' + rdbox_app_market.config.get('kubernetes', 'common_cert') + '\n'

    def filter_tlsHosts(self):
        need_to_skip_next = []
        target_data = ''
        for index, line, _, structure in self.generator():
            if len(need_to_skip_next) > 0:
                if re.match(r'^\s*#+', line):
                    self.lines[index] = line
                else:
                    self.lines[index] = '#' + line
                    need_to_skip_next.pop()
                    if len(need_to_skip_next) == 0:
                        self.lines_insert(index + 1, target_data)
            if re.match(r'^\s*#*-*\s*tlsHosts:', line):
                hosts_item = self.ingress_dicts.get('.'.join(structure.parent())).get('hosts', [{}])[0].get('tlsHosts', None)
                if hosts_item is None:
                    self.lines[index] = line
                    continue
                if len(hosts_item) == 0:
                    self.lines[index] = re.sub(r'(^\s*-*\s*)(tlsHosts:\s[\[\]\.\_\-\"\'\/a-zA-Z0-9]*\n)', r'\1', line) + 'tlsHosts:' + '\n'
                    self.lines_insert(index + 1, re.sub(r'(^\s*-*\s*)(tlsHosts:\s[\[\]\.\_\-\"\'\/a-zA-Z0-9]*\n)', r'\1', line) + ' ' * self.indent_unit + '- ' + '"*.' + rdbox_app_market.config.get('kubernetes', 'common_domain') + '"' + '\n')
                elif len(hosts_item) > 0:
                    self.lines[index] = re.sub(r'(^\s*-*\s*)(tlsHosts:\s[\[\]\.\_\-\"\'\/a-zA-Z0-9]*\n)', r'\1', line) + 'tlsHosts:' + '\n'
                    target_data = re.sub(r'(^\s*-*\s*)(tlsHosts:\s[\[\]\.\_\-\"\'\/a-zA-Z0-9]*\n)', r'\1', line) + ' ' * self.indent_unit + '- ' + '"*.' + rdbox_app_market.config.get('kubernetes', 'common_domain') + '"' + '\n'
                    need_to_skip_next = range(len(hosts_item))
            else:
                continue


class FilterOfStrHostsIngress(BaseFilterOfIngress):
    def __init__(self, module_name: str, lines: list, ingress_dicts: dict):
        super().__init__(module_name, lines, ingress_dicts)

    def filter(self):
        self.filter_enabled()
        self.filter_annotations()
        self.filter_tls()
        self.filter_hosts()
        return self.lines

    def filter_hosts(self):
        need_to_skip_next = []
        target_data = ''
        for index, line, now_indent, structure in self.generator():
            if len(need_to_skip_next) > 0:
                if re.match(r'^\s*#+', line):
                    self.lines[index] = line
                else:
                    self.lines[index] = '#' + line
                    need_to_skip_next.pop()
                    if len(need_to_skip_next) == 0:
                        self.lines_insert(index + 1, target_data)
            if re.match(r'^\s*hosts:', line):
                hostname = self.build_hostname(structure)
                hosts_item = self.ingress_dicts.get('.'.join(structure.parent())).get('hosts', None)
                if hosts_item is None:
                    self.lines[index] = line
                    self.lines_insert(index + 1, ' ' * now_indent + ' ' * self.indent_unit + '- ' + hostname + '\n')
                    continue
                if len(hosts_item) == 0:
                    self.lines[index] = ' ' * now_indent + 'hosts:' + '\n'
                    self.lines_insert(index + 1, ' ' * now_indent + ' ' * self.indent_unit + '- ' + hostname + '\n')
                elif len(hosts_item) > 0:
                    self.lines[index] = line
                    target_data = ' ' * now_indent + ' ' * self.indent_unit + '- ' + hostname + '\n'
                    need_to_skip_next = list(range(len(hosts_item)))
            else:
                continue

    def filter_tls(self):
        for index, line, now_indent, structure in self.generator():
            if re.match(r'^\s*tls:', line):
                tls_item = self.ingress_dicts.get('.'.join(structure.parent())).get('tls', None)
                hosts_item = '*.' + rdbox_app_market.config.get('kubernetes', 'common_domain')
                if tls_item is None:
                    self.lines[index] = line
                    content = yaml.dump([{'secretName': rdbox_app_market.config.get('kubernetes', 'common_cert'), 'hosts': [hosts_item]}], indent=self.indent_unit)
                    for i, text in enumerate(content.split('\n')):
                        if text != '':
                            self.lines_insert(index + i + 1, ' ' * now_indent + ' ' * self.indent_unit + text + '\n')
                    continue
                if len(tls_item) == 0:
                    self.lines[index] = ' ' * now_indent + 'tls:' + '\n'
                    content = yaml.dump([{'secretName': rdbox_app_market.config.get('kubernetes', 'common_cert'), 'hosts': [hosts_item]}], indent=self.indent_unit)
                    for i, text in enumerate(content.split('\n')):
                        if text != '':
                            self.lines_insert(index + i + 1, ' ' * now_indent + ' ' * self.indent_unit + text + '\n')
                    continue
                elif len(tls_item) > 0:
                    self.lines[index] = line
                    continue
            else:
                continue


class FilterOfNodeSelector(object):
    def __init__(self, module_name: str, lines: List[str]):
        """Filter of ingress

        Args:
            module_name (str): module name
            lines (list): A list of values.yaml divided by a new line
        """
        self.module_name = module_name
        self.lines = lines
        self.node_selector_indent = 0
        self.is_nodeSelector_in_processing = False
        self.original_nodeSelector_text = ''
        self.multi_arch_dict = self.get_multi_arch_dict(lines)

    def get_multi_arch_dict(self, lines: List[str]) -> Dict[str, str]:
        """Get a dict of images that support multi-architectures.

        The dockerhub allows you to get the architecture of the image with a REST API.

        Args:
            lines (List[str]): A list of values.yaml divided by a new line

        Returns:
            Dict[str, str]: key is Dot-separated characters indicate a layer. value is URI of a repository on the dockerhub.
        """
        multi_arch_dict = {}
        obj_values = yaml.safe_load('\n'.join(lines))
        node_selector_list = [i for i, line in enumerate(lines) if re.match(r'^\s*nodeSelector:', line)]
        image_list = [i for i, line in enumerate(lines) if re.match(r'^\s*image:', line)]
        if len(node_selector_list) == len(image_list):
            all_image_list = Util.has_key_recursion_full(obj_values, 'image')
            for struct, image_dict in all_image_list.items():
                repo_uri = image_dict.get('repository', image_dict.get('name', ''))
                if self.__is_hosted_on_dockerhub(repo_uri):
                    url = self.__build_url_of_dockerhub(image_dict, repo_uri)
                    if self.__has_multiarch_image(url):
                        multi_arch_dict.setdefault(struct, repo_uri)
        return multi_arch_dict

    def is_processing(self):
        return self.is_nodeSelector_in_processing

    def filter(self):
        file_text = ''
        self.indent_list, self.indent_unit = self.__get_indent_info(self.lines)
        structure = Structure(self.indent_unit)
        for i, line in enumerate(self.lines):
            now_indent = self.indent_list[i]
            now_struct_str = structure.update(line, now_indent)
            if self.is_nodeSelector_in_processing:
                if structure.get_struct()[-1] == 'nodeSelector':
                    now_struct_str = '.'.join(structure.get_struct()[:-1])
                is_multi_arch = now_struct_str in self.multi_arch_dict
                file_text += self.__filter(line, now_indent, is_multi_arch)
            else:
                file_text += self.__filter(line, now_indent)
        return file_text, True

    def __filter(self, line, indent, is_multi_arch=False):
        if self.is_nodeSelector_in_processing:
            return self.__processing_of_block_elements(line, is_multi_arch)
        else:
            if self.__is_start_of_block_element(line, indent):
                return ''
            else:
                return line

    def __is_start_of_block_element(self, line, indent):
        if re.match(r'^\s*nodeSelector:', line):
            self.is_nodeSelector_in_processing = True
            self.original_nodeSelector_text += line
            self.node_selector_indent = indent
            return True
        return False

    def __processing_of_block_elements(self, line, is_multi_arch=False):
        file_text = ''
        if re.match(r'^\s*\n', line) or re.match(r'^\s*[0-9a-zA-Z]*:', line) or re.match(r'^\s*#', line):
            nodeSelector_obj = yaml.safe_load(self.original_nodeSelector_text)
            if not isinstance(nodeSelector_obj.get('nodeSelector'), dict):
                nodeSelector_obj = {'nodeSelector': {}}
            nodeSelector_obj.get('nodeSelector').setdefault('beta.kubernetes.io/os', 'linux')
            if not is_multi_arch:
                nodeSelector_obj.get('nodeSelector').setdefault('beta.kubernetes.io/arch', 'amd64')
            else:
                pass
            aligned_nodeSelector_text = yaml.dump(nodeSelector_obj, indent=self.indent_unit)
            for text in aligned_nodeSelector_text.split('\n'):
                if text != '':
                    file_text = file_text + ' ' * self.node_selector_indent + text + '\n'
            self.__reset()
            file_text += line
        else:
            self.original_nodeSelector_text += line
        return file_text

    def __reset(self):
        self.is_nodeSelector_in_processing = False
        self.original_nodeSelector_text = ''

    def __is_hosted_on_dockerhub(self, repo_url):
        repo_url_list = repo_url.split('/')
        if len(repo_url_list) <= 2:
            return True
        else:
            return False

    def __build_url_of_dockerhub(self, image_tag_dict, repo_uri):
        uri = repo_uri
        repo_url_list = repo_uri.split('/')
        if len(repo_url_list) == 1:
            uri = 'library' + '/' + repo_uri
        url = 'https://hub.docker.com/v2/repositories/{uri}/tags/{tag}'.format(uri=uri, tag=image_tag_dict.get('tag'))
        return url

    def __has_multiarch_image(self, url):
        has_arch_arm = False
        r = requests.get(url)
        if r.status_code == requests.codes.ok:
            data = r.json()
            for v in data.get('images', []):
                if v.get('architecture').startswith('arm'):
                    has_arch_arm = True
        return has_arch_arm

    def __get_indent_info(self, lines):
        il = IndentList()
        for line in lines:
            il.add_with_line_of_text(line)
        return il.to_list(), il.get_unit_indent_length()


class Structure(object):
    def __init__(self, indent_unit):
        self.struct = ['_']
        self.indent_unit = indent_unit
        self.prev_indent = 0
        self.prev_line_without_comment = ''

    def get_struct(self):
        return self.struct

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

    def parent(self):
        return self.struct[:-1]


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
        indent_length_of_processing_line = self.__get_indent_length_of_target(line)
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

    def __get_indent_length_of_target(self, line):
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
            if self.__is_start_of_block_element(line, indent_length_of_processing_line):
                return True
        return self.__processing_of_block_elements(indent_length_of_processing_line)

    def __is_start_of_block_element(self, line, indent_length_of_processing_line):
        if re.match(self.regex, line):
            self.is_block_of_yaml_in_processing = True
            if self.indent_length_of_block_of_yaml == -1:
                self.indent_length_of_block_of_yaml = indent_length_of_processing_line
            return True
        return False

    def __processing_of_block_elements(self, indent_length_of_processing_line):
        if self.is_block_of_yaml_in_processing and indent_length_of_processing_line >= 0:
            if indent_length_of_processing_line > self.indent_length_of_block_of_yaml:
                # countinue
                return True
            else:
                # end
                self.__reset()
                return False
        return False

    def __reset(self):
        self.is_block_of_yaml_in_processing = False
        self.indent_length_of_list_of_yaml = -1
