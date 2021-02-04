#! /usr/bin/python3

"""
List all packages and it's contents into one json file.
From https://github.com/praiskup/dnf-hacks/blob/main/list_all_packages.py

HOWTO: Precreate BaseOS, AppStream and PowerTools directories somewhere, and run
the following shell snippet:

for a in *; do mkdir $a/repodata; done
for repo in *; do
    pushd $repo/repodata
    # lftp -e "mirror ; exit" http://mirror.centos.org/centos/8/$repo/x86_64/os/repodata/
    lftp -e "mirror ; exit" https://vault.centos.org/8.2.2004/$repo/x86_64/os/repodata/
    popd
done
"""

import argparse
import logging
import json
import os
import re

import dnf
import hawkey


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
            module_hotfixes=1,
        )

    assert found

    # read the metadata
    base.fill_sack()
    return base


def _main():
    """
    {
        "basename": {
            "rpm": ...,
            "sha256": ...,
            "license": ...,
            "srpm": ...,
            "file-provides": [],
            "provides": [],
            "requires": [],
            "url": "download_url",
            "file-requires": [], # drop ??
            "modularitylabel": "", # reference metadata don't match reality
        }
    }
    """

    parser = _get_arg_parser()
    args = parser.parse_args()
    dnf_base = _init_and_get_dnf(args.repos)

    query = dnf_base.sack.query().filter(reponame__neq="@System")
    packages = {}

    # We parse modular metadata separately from normal metadata, and if we want
    # to assign the modularitylabel back to the packages (artifacts) we have to
    # be able to search in the "packages" dictionary quickly using the artifacts
    # format (nevra).
    map_by_artifact_name = {}

    for package in query:
        basename = os.path.basename(package.location)
        if basename in packages:
            LOG.error("package %s is duplicated", basename)
            continue
        pkgdata = {}
        pkgdata["rpm"] = basename
        pkgdata["license"] = package.license
        assert hawkey.chksum_name(package.chksum[0]) == "sha256"
        pkgdata["sha256"] = package.chksum[1].hex()
        pkgdata["srpm"] = package.sourcerpm
        pkgdata["requires"] = [str(r) for r in package.requires]
        pkgdata["provides"] = [str(r) for r in package.provides]
        pkgdata["file-provides"] = package.files
        pkgdata["url"] = package.remote_location()

        packages[basename] = pkgdata

        lookup_string = "{}-{}:{}-{}.{}".format(
            package.name, package.epoch, package.version, package.release,
            package.arch,
        )

        assert lookup_string not in map_by_artifact_name
        map_by_artifact_name[lookup_string] = pkgdata

    mbase = dnf.module.module_base.ModuleBase(dnf_base)
    for module in mbase.get_modules('*')[0]:
        artifacts = module.getArtifacts()
        module = module.getFullIdentifier()
        for artifact in artifacts:
            try:
                package = map_by_artifact_name[artifact]
            except KeyError:
                if artifact.endswith(".src"):
                    continue
                if "debuginfo" in artifact:
                    continue
                if "debugsource" in artifact:
                    continue
                raise

            assert "modularitylabel" not in package
            package["modularitylabel"] = module

    # check that all seemingly modular packages have modularitylabel
    for package in packages:
        if ".module_" in package:
            assert "modularitylabel" in packages[package]

    print(json.dumps(packages))

if __name__ == "__main__":
    _main()
