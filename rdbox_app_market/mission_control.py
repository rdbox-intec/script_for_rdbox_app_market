#!/usr/bin/env python3

from rdbox_app_market.github import ReferenceGithubRepos, Collector, Publisher


class MissionControl(object):
    @classmethod
    def launch(cls):
        repo = ReferenceGithubRepos('https://github.com/bitnami/charts', 'bitnami', True)
        collector = Collector(repo)
        isolations_collect_result, dependons_collect_result = collector.work()
        print('---')
        converter = Publisher(isolations_collect_result, dependons_collect_result)
        converter.work()
