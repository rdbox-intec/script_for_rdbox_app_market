#!/usr/bin/env python3
import os
import shutil

from logging import getLogger

from rdbox_app_market.github import GithubRepos, ReferenceGithubRepos
from rdbox_app_market.app_market import Collector, Publisher

r_logger = getLogger('rdbox_cli')
r_print = getLogger('rdbox_cli').getChild("stdout")


class MissionControl(object):
    @classmethod
    def launch(cls):
        top_dir_path = GithubRepos.TOP_DIR
        try:
            shutil.rmtree(top_dir_path)
        except FileNotFoundError:
            os.makedirs(top_dir_path, exist_ok=True)
        # ----------------- #
        try:
            repos = []
            repos.append(ReferenceGithubRepos(
                'https://github.com/bitnami/charts.git',
                'master',
                specific_dir_from_top='bitnami',
                check_tldr=True,
                priority=999))
            repos.append(ReferenceGithubRepos(
                'https://github.com/helm/charts.git',
                'master',
                specific_dir_from_top='stable',
                check_tldr=False,
                priority=500))
            # ----------------- #
            collector = Collector(repos)
            isolations_collect_result, dependons_collect_result = collector.work()
            publisher = Publisher(isolations_collect_result, dependons_collect_result)
            _ = publisher.work()
        except Exception:
            import traceback
            r_logger.error(traceback.format_exc())
