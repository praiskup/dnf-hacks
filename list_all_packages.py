#! /usr/bin/python3

"""
list all packages and it's details into one file

Precreate BaseOS, AppStream and PowerTools directories somewhere, and run
the following shell snippet:

for repo in *; do
    pushd $repo/repodata
    lftp -e "mirror ; exit" http://mirror.centos.org/centos/8/$repo/x86_64/os/repodata/
    popd
done
"""

import argparse
import logging
import re

import dnf


logging.basicConfig(format='%(levelname)s: %(message)s')
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


def _get_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", action='append', dest="repos", required=True)
    return parser


def url_to_repoid(repo_url):
    """
    Taken from: https://pagure.io/copr/copr/blob/\
                0ea325a9249fd4570e2d380f30432ff8f90290e8/f/\
                frontend/coprs_frontend/coprs/helpers.py#_477-482
    """
    repo_url = re.sub("[^a-zA-Z0-9]", '_', repo_url)
    repo_url = re.sub("(__*)", '_', repo_url)
    repo_url = re.sub("(_*$)|^_*", '', repo_url)
    return repo_url


def _init_and_get_dnf(repos):
    base = dnf.Base()
    base.read_all_repos()

    # disable all pre-configured repos
    base.repos.get_matching('*').disable()

    found = 0
    for repo in repos:
        reponame = url_to_repoid(repo)
        LOG.info("Using repo ID %s => %s", reponame, repo)
        found += 1
        base.repos.add_new_repo(
            reponame,
            base.conf,
            baseurl=(repo,),
        )

    assert found

    # read the metadata
    base.fill_sack()
    return base


def _main():
    parser = _get_arg_parser()
    args = parser.parse_args()
    dnf_base = _init_and_get_dnf(args.repos)

    query = dnf_base.sack.query().filter(reponame__neq="@System")
    all_packages = list(query)
    #import ipdb
    #ipdb.set_trace()
    for package in all_packages:
        print("{} {} {} {} {}".format(package.name, package.version,
            package.release, package.repoid, package.arch))


if __name__ == "__main__":
    _main()
