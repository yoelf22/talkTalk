-- Desktop launcher: starts talkTalk if :8795 is down, then opens it in Chrome.
-- Build: osacompile -o ~/Desktop/talkTalk.app launcher.applescript
do shell script "$HOME/Projects/WEB/talkTalk/run.sh > /dev/null 2>&1"
