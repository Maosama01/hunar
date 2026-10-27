#!/bin/sh
# Push to the project remote (github.com/Maosama01/hunar) using the Maosama01 gh login,
# without changing the active gh account or global git config.
set -e
TOKEN=$(gh auth token --user Maosama01)
git -c credential.helper= -c "credential.helper=!f() { echo username=x-access-token; echo password=$TOKEN; }; f" push "$@"
