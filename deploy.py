#!/usr/bin/env python

import subprocess
subprocess.Popen('git push', shell=True).wait()
subprocess.Popen('git push heroku master', shell=True).wait()
