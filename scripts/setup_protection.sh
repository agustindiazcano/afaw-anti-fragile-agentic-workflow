#!/bin/bash
set -e

# setup_protection.sh
# This script applies GitHub branch protection rules to the 'main' branch using the GitHub CLI (gh).
#
# Configuration:
# - Requires a PR before merging.
# - Enforces checks for administrators (ensures no bypass without CI passing).
# - Sets required approvals to 0: this is optimized for an AI-agent "solo use" workflow
#   where the human acts as the reviewer and approver, but technically GitHub allows a
#   PR to be merged by the owner if approvals are 0, while still forcing CI to pass.
#   (If you want strict approvals, change --required-approvals 1).
# - Requires specific status checks to pass before merging:
#   * 'lint' (from scripts-ci.yml)
#   * 'typecheck' (from scripts-ci.yml)
#   * 'tests' (from scripts-ci.yml)
#   * 'task-delta' (from task-delta-check.yml)

echo "Setting up branch protection for 'main'..."

gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  /repos/{owner}/{repo}/branches/main/protection \
  -f "enforce_admins=true" \
  -f "required_pull_request_reviews[required_approving_review_count]=0" \
  -f "required_pull_request_reviews[dismiss_stale_reviews]=false" \
  -f "required_pull_request_reviews[require_code_owner_reviews]=false" \
  -f "required_status_checks[strict]=true" \
  -f "required_status_checks[contexts][]=lint" \
  -f "required_status_checks[contexts][]=typecheck" \
  -f "required_status_checks[contexts][]=tests" \
  -f "required_status_checks[contexts][]=task-delta" \
  -f "restrictions=null" \
  -F "required_linear_history=false" \
  -F "allow_force_pushes=false" \
  -F "allow_deletions=false"

echo "Branch protection applied."
