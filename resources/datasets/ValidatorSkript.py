from subprocess import Popen, PIPE, STDOUT

p = Popen(['java', '-jar', 'validator.jar'], stdout=PIPE, stderr=STDOUT)
for line in p.stdout:
    print(line)