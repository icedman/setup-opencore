#!/usr/bin/python

import json
import os
import subprocess

f = open('./sources.json')
sources = json.load(f)

def download(url, file, info):
	sx = os.path.splitext(file)
	filename = sx[0]
	extension = sx[1]

	if not os.path.isfile(file) and extension == '.zip':
		subprocess.call(['wget', '-P', os.path.dirname(file), url])

	if not os.path.isdir(file) and extension == '':
		os.chdir(os.path.dirname(file))
		subprocess.call(['git', 'clone', url ])
		os.chdir('../')

	if os.path.isfile(file) and extension == '.zip':
		os.chdir(os.path.dirname(file))

		if not os.path.isdir(info['name']):
			os.mkdir(info['name'])

		os.chdir(info['name'])
		subprocess.call(['unzip',  '-n', '../' + os.path.basename(file)])

		os.chdir('../../')

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
		download(t['url'], target, t)

	# apply our patches
	subprocess.call(['patch', '-fs', './tools/GenSMBIOS/GenSMBIOS.command', './patches/genbios.patch'])
	

def downloadKexts ():
	for t in sources['kexts']:
		target = os.path.join('./kexts', os.path.basename(t['url']))
		download(t['url'], target, t)

def prepareBaseEFI ():
	subprocess.call(['cp',  '-R', './tools/opencore/X64/EFI', './'])
	subprocess.call(['cp',  './tools/opencore/Docs/Sample.plist', './EFI/OC/config.plist'])

if not os.path.isdir('./tools') and not os.path.isdir('./kexts'):
	prepare()

if not os.path.isdir('./EFI'):
	prepareBaseEFI()

