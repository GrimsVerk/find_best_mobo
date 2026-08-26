#!/bin/bash
MB=88400b8036bb20b4a2eb6233d98731f4821a4723
IDRE='(BL|OD|ESC|RN)-[0-9]+|(R|V|S|F)[0-9]+'
for sha in $(git log --reverse --format='%H' $MB..$1); do
  echo "@@@COMMIT $sha"
  git log -1 --date=format-local:'%Y-%m-%dT%H:%M:%SZ' --format='cdate=%cd%nadate=%ad%nauthor=%an%nparents=%P%nsubject=%s' $sha
  echo "coauth=$(git log -1 --format='%b' $sha | grep -i '^Co-Authored-By:' | head -1 | sed 's/^Co-Authored-By: *//')"
  echo "--files--"
  git show --pretty=format: --name-only -m --first-parent $sha | grep -v '^$' | sort -u
  echo "--ids-subject--"
  git log -1 --format='%s' $sha | grep -owE "$IDRE" | sort -u
  echo "--ids-diff--"
  git show --pretty=format: --unified=0 -m --first-parent $sha | grep '^+' | grep -owE "$IDRE" | sort -u | tr '\n' ' '
  echo
  echo "--ids-body--"
  git log -1 --format='%b' $sha | grep -owE "$IDRE" | sort -u | tr '\n' ' '
  echo
  echo "--ranges--"
  { git show --pretty=format: --unified=0 -m --first-parent $sha | grep '^+';
    git log -1 --format='%s%n%b' $sha; } \
    | grep -oE '(BL|OD|ESC|RN)-[0-9]+ *(\.\.|through) *((BL|OD|ESC|RN)-)?[0-9]+|(R|V|S|F)[0-9]+ *(\.\.|-|through) *(R|V|S|F)?[0-9]+' \
    | sort -u
  echo "--endcommit--"
done
