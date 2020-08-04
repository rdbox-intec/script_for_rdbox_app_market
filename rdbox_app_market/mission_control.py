#!/usr/bin/env python3
import os
import shutil

from rdbox_app_market.github import ReferenceGithubRepos
from rdbox_app_market.app_market import Collector, Publisher


class MissionControl(object):
    @classmethod
    def launch(cls):
        top_dir_path = os.path.join('/tmp', '.original.charts')
        try:
            shutil.rmtree(top_dir_path)
        except FileNotFoundError:
            os.makedirs(top_dir_path, exist_ok=True)
        repos = []
        repos.append(ReferenceGithubRepos('https://github.com/bitnami/charts.git', 'master', 'bitnami', True, 999))
        repos.append(ReferenceGithubRepos('https://github.com/helm/charts.git', 'master', 'stable', False, 500))
        # ----------------- #
        collector = Collector(repos)
        isolations_collect_result, dependons_collect_result = collector.work()
        publisher = Publisher(isolations_collect_result, dependons_collect_result)
        _ = publisher.work()
