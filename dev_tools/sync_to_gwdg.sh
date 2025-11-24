#!/bin/bash
#
# This script syncs the local repository with the GWDG remote repository.
# It requires that you have added a remote named 'gwdg' pointing to the GWDG repository, e.g.:
#
#    git remote add gwdg https://gitlab.gwdg.de/yourusername/yourrepo.git
#
git pull origin main
git push gwdg main