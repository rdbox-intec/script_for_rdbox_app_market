#!/usr/bin/env python3
import os
import shutil
import yaml
import subprocess


class HelmCommand(object):
    """Wrapped HELM command used by rdbox_app_market.

    Attributes:
        helm (str): Full path of platform-specific helm commands.
    """

    def __init__(self):
        import platform
        pf = platform.system()
        if pf == 'Darwin':
            # By Brew
            self.helm = os.path.join('/usr', 'local', 'bin', 'helm')
        elif pf == 'Linux':
            # By Snap
            self.helm = os.path.join('/snap', 'bin', 'helm')
        else:
            # Setuped PATH
            self.helm = 'helm'

    def template(self, specific_dir_path, module_name, set_list=[]):
        cmd_list = []
        module_dir_path = os.path.join(specific_dir_path, module_name)
        cmd_list.append(self.helm)
        cmd_list.append('template')
        cmd_list.append(module_dir_path)
        if len(set_list) > 0:
            set_str = ''
            for set_item in set_list:
                set_str = set_str + '--set' + ' ' + set_item.replace('[', '\[').replace(']', '\]') + '=DUMMY' + ' '        # noqa: W605
            cmd_list.append(set_str)
        cmd_list = ' '.join(cmd_list)
        if os.path.isdir(os.path.join(module_dir_path, 'templates', 'tests')):
            shutil.move(os.path.join(module_dir_path, 'templates', 'tests'), os.path.join(module_dir_path, '_tests'))
            ret = subprocess.run(cmd_list, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)
            shutil.move(os.path.join(module_dir_path, '_tests'), os.path.join(module_dir_path, 'templates', 'tests'))
        else:
            ret = subprocess.run(cmd_list, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=True)
        chart_map = {}
        for chart in ret.stdout.split('---'):
            if chart.startswith('\n#'):
                chart_lines = chart.split('\n')
                filename = chart_lines[1].split(' ')[2]
                body = yaml.safe_load('\n'.join(chart_lines[2:]))
                chart_map.setdefault(filename, body)
        return chart_map

    def package(self, specific_dir_path, module_name, dest_dir_path):
        path_of_generation_result = ''
        cmd_list = []
        module_dir_path = os.path.join(specific_dir_path, module_name)
        cmd_list.append(self.helm)
        cmd_list.append('package')
        cmd_list.append(module_dir_path)
        cmd_list.append('--destination')
        cmd_list.append(dest_dir_path)
        ret = subprocess.run(cmd_list, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if ret.returncode == 0:
            path_of_generation_result = ret.stdout.split('it to: ')[-1].strip()
        else:
            path_of_generation_result = ret.stderr
        return path_of_generation_result

    def repo_index(self, specific_dir_path):
        path_of_generation_result = ''
        cmd_list = []
        cmd_list.append(self.helm)
        cmd_list.append('repo')
        cmd_list.append('index')
        cmd_list.append(specific_dir_path)
        ret = subprocess.run(cmd_list, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if ret.returncode == 0:
            path_of_generation_result = os.path.join(specific_dir_path, 'index.yaml')
        else:
            path_of_generation_result = ret.stderr
        return path_of_generation_result
