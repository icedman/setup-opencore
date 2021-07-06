#!/usr/bin/python

import json
import os
import subprocess

f = open('./sources.json')
sources = json.load(f)

def download(url, file):
	extension = os.path.splitext(file)[1]

	if not os.path.isfile(file) and extension == '.zip':
		subprocess.call(['wget', '-P', os.path.dirname(file), url])

	if not os.path.isdir(file) and extension == '':
		os.chdir(os.path.dirname(file))
		subprocess.call(['git', 'clone', url ])
		os.chdir('../')

	if os.path.isfile(file) and extension == '.zip':
		os.chdir(os.path.dirname(file))
		subprocess.call(['unzip',  '-n', os.path.basename(file)])
		os.chdir('../')

def prepare ():
	if not os.path.isdir('./tools'):
		os.mkdir('./tools')
	if not os.path.isdir('./kexts'):
		os.mkdir('./kexts')
		
	downloadTools()
	downloadKexts()

def downloadTools ():
	for t in sources['tools']:
		target = os.path.join('./tools', os.path.basename(t['url']))
		download(t['url'], target)

	# apply our patches
	subprocess.call(['patch', './tools/GenSMBIOS/GenSMBIOS.command', './patches/genbios.patch'])
	

def downloadKexts ():
	for t in sources['kexts']:
		target = os.path.join('./kexts', os.path.basename(t['url']))
		download(t['url'], target)

def prepareBaseEFI ():
	if not os.path.isdir('./EFI'):
		subprocess.call(['cp',  '-R', './tools/X64/EFI', './'])
		subprocess.call(['cp',  './tools/Docs/Sample.plist', './EFI/OC/config.plist'])

prepare()
prepareBaseEFI()
