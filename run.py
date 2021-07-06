#!/usr/bin/python3

import json
import os
import subprocess
import sys

from xml.dom import minidom

sources = json.load(open('./sources.json'))

def grab (prompt):
	sys.stdout.write(prompt + ":")
	sys.stdout.flush()
	i = sys.stdin.readline().strip()
	return i
 
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

def findByKey(relative, key):
	for k in relative.childNodes:
		if k.nodeName == 'key' and k.firstChild.nodeValue.strip() == key:
			if k.nextSibling.nodeName == 'dict':
				return k.nextSibling
			else:
				return k.nextSibling.nextSibling
	return None

def updateSMBIOS() :
	smbios = json.load(open('./smbios.json'))
	pi = findByKey(d, 'PlatformInfo')
	gen = findByKey(pi, 'Generic')
	mod = findByKey(gen, 'MLB')
	mod.firstChild.nodeValue = smbios['BoardSerial']
	mod = findByKey(gen, 'SystemProductName')
	mod.firstChild.nodeValue = smbios['Type']
	mod = findByKey(gen, 'SystemSerialNumber')
	mod.firstChild.nodeValue = smbios['Serial']
	mod = findByKey(gen, 'SystemUUID')
	mod.firstChild.nodeValue = smbios['SmUUID']

# load config

root = minidom.parse('./EFI/OC/config.plist')
d = root.documentElement.getElementsByTagName('dict')[0]

updateSMBIOS()

# load save

f = open("./EFI/OC/config.plist", "w")
f.write(root.toxml())



# grab('hello')


