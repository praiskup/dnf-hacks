#! /usr/bin/python3

"""
When source RPM and the corresponding binary RPMs are put in the same result
directory, this script is able to parse the repository metadata and pair the
existing source RPM with set of binary RPMs.  Per discussion in:
https://pagure.io/prunerepo/issue/7
"""

import os
import sys

import dnf

base = dnf.Base()
base.read_all_repos()

# disable all pre-configured repos
repos = base.repos.get_matching('*')
repos.disable()

if len(sys.argv) < 2:
    sys.stderr.write("one argument expected - repourl\n")
    sys.exit(1)

base.repos.add_new_repo(
    "test",
    base.conf,
    baseurl=(sys.argv[1],),
)

# read the remote metadata
base.fill_sack()

# query the metadata
query = base.sack.query()
remote = query.filter(reponame__neq="@System")
available_packages = list(remote)

found_srpms = set()
found_mapping = {}

# list all packages
for package in available_packages:
    if package.sourcerpm:
        # handling source RPMs only for now
        continue

    # handling source RPM
    found_srpms.add(os.path.normpath(package.relativepath))

# group the binary RPMs
for package in available_packages:
    if not package.sourcerpm:
        continue  # only binary RPMs now..

    dirname = os.path.dirname(os.path.normpath(package.relativepath))
    expected_source_rpm = os.path.join(dirname, package.sourcerpm)

    if not expected_source_rpm:
        sys.stderr.write(f"error: {package.relativepath} has no SRPM header\n")
        continue

    if expected_source_rpm not in found_srpms:
        sys.stderr.write(f"error: {package.relativepath} has no source RPM in the directory\n")
        continue

    if not expected_source_rpm in found_mapping:
        found_mapping[expected_source_rpm] = set()

    found_mapping[expected_source_rpm].add(package.relativepath)

for srpm, rpms in found_mapping.items():
    print(srpm)
    for rpm in rpms:
        print(f"    {rpm}")
