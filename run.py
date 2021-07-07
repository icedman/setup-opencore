#!/usr/bin/python3

import json
import os
import subprocess
import sys

from xml.dom import minidom

sources = json.load(open('./sources.json'))

def _log(t):
	print(t)

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

def findByKey(root, key):
	nodes = root.getElementsByTagName('key')
	for k in nodes:
		if k.nodeName == 'key' and k.firstChild.nodeValue.strip() == key:
			return k
	return None

def findByStringValue(root, str):
	nodes = root.getElementsByTagName('string')
	for k in nodes:
		if k.nodeName == 'string' and k.firstChild and k.firstChild.nodeValue.strip() == str:
			return k
	return None

def findByChildKey(relative, key):
	nodes = relative.childNodes
	for k in nodes:
		if k.nodeName == 'key' and k.firstChild.nodeValue.strip() == key:
			if not k.nextSibling.nodeName == '#text':
				return k.nextSibling
			else:
				return k.nextSibling.nextSibling
	return None

def createNodeValue(root, tag, value):
	entry = root.createElement(tag)
	if value:
		entry.appendChild(root.createTextNode(value))
	return entry

def updateSMBIOS(root) :
	if not os.path.isfile('./smbios.json'):
		print('ERROR: smbios.json config not found. Run ./tool/GenSMBIOS/GenSMBIOS.command\n')
		return

	smbios = json.load(open('./smbios.json'))

	d = root.documentElement.getElementsByTagName('dict')[0]
	pi = findByChildKey(d, 'PlatformInfo')
	gen = findByChildKey(pi, 'Generic')

	for k in smbios:
		mod = findByChildKey(gen, k)
		mod.firstChild.nodeValue = smbios[k]

def updateDeviceProperties(root):
	d = root.documentElement.getElementsByTagName('dict')[0]
	dev = findByChildKey(d, 'DeviceProperties')
	add = findByChildKey(dev, 'Add')

	if not os.path.isfile('./gpu.json'):
		print('ERROR: gpu.json config not found. Copy sample from /docs\n')
		return

	# gpu
	gpu = findByChildKey(add, 'PciRoot(0x0)/Pci(0x2,0x0)')
	if not gpu:
		gpu = root.createElement('key')
		gpu.appendChild(root.createTextNode('PciRoot(0x0)/Pci(0x2,0x0)'))
		add.appendChild(gpu)
		props = root.createElement('dict')
		add.appendChild(props)
		gpu = props

	gpuProps = json.load(open('./gpu.json'))
	for k in gpuProps:
		mod = findByChildKey(gpu, k)
		value = gpuProps[k]
		valueType = 'string'

		if type(gpuProps[k]) is dict:
			value = gpuProps[k]['value']
			valueType = gpuProps[k]['type']

		if mod:
			mod.firstChild.nodeValue = value
		else:
			mod = root.createElement('key')
			mod.appendChild(root.createTextNode(k))
			gpu.appendChild(mod)
			mod = root.createElement(valueType)
			mod.appendChild(root.createTextNode(value))
			gpu.appendChild(mod)

def updateKexts (root):
	subprocess.call(['rm', '-rf', './EFI/OC/Kexts/*' ])

	if not os.path.isfile('./kexts.json'):
		print('ERROR: kexts.json config not found. Copy sample from /docs\n')
		return

	d = root.documentElement.getElementsByTagName('dict')[0]
	kn = findByChildKey(d, 'Kernel')
	add = findByChildKey(kn, 'Add')

	# disable everything
	for entry in add.getElementsByTagName('dict'):
		enabled = findByChildKey(entry, 'Enabled')
		enabled.tagName = 'false'


	kexts = json.load(open('./kexts.json'))
	for k in kexts['kexts']:
		subprocess.call(['cp', '-r', k['path'], './EFI/OC/Kexts/'])

		kextName = os.path.basename(k['path'])
		entry = findByStringValue(root, kextName)

		execPath = 'Contents/MacOS/' + os.path.splitext(kextName)[0]
		execRealPath = './EFI/OC/Kexts/' + kextName + '/' + execPath
		if not os.path.isfile(execRealPath):
			execPath = ''

		plistPath = 'Contents/Info.plist'
		plistRealPath = './EFI/OC/Kexts/' + kextName + '/' + plistPath
		if not os.path.isfile(plistRealPath):
			plistPath = ''

		print(plistRealPath)

		if entry:
			parent = entry.parentNode
			enabled = findByChildKey(entry.parentNode, 'Enabled')
			enabled.tagName = 'true'
			_log(kextName + ' enabled')
		else:
			entry = root.createElement('dict')
			entry.appendChild(createNodeValue(root, 'key', 'Arch'))
			entry.appendChild(createNodeValue(root, 'string', 'x86_64'))
			entry.appendChild(createNodeValue(root, 'key', 'BundlePath'))
			entry.appendChild(createNodeValue(root, 'string', kextName))
			entry.appendChild(createNodeValue(root, 'key', 'Enabled'))
			entry.appendChild(createNodeValue(root, 'true', None))
			entry.appendChild(createNodeValue(root, 'key', 'ExecutablePath'))
			entry.appendChild(createNodeValue(root, 'string', execPath))
			entry.appendChild(createNodeValue(root, 'key', 'MaxKernel'))
			entry.appendChild(createNodeValue(root, 'string', ''))
			entry.appendChild(createNodeValue(root, 'key', 'MinKernel'))
			entry.appendChild(createNodeValue(root, 'string', ''))
			entry.appendChild(createNodeValue(root, 'key', 'PlistPath'))
			entry.appendChild(createNodeValue(root, 'string', plistPath))
			add.appendChild(entry)
			_log(kextName + ' added')

		# <dict>
		# 	<key>Arch</key>
		# 	<string>x86_64</string>
		# 	<key>BundlePath</key>
		# 	<string>Lilu.kext</string>
		# 	<key>Comment</key>
		# 	<string>Patch engine</string>
		# 	<key>Enabled</key>
		# 	<true/>
		# 	<key>ExecutablePath</key>
		# 	<string>Contents/MacOS/Lilu</string>
		# 	<key>MaxKernel</key>
		# 	<string/>
		# 	<key>MinKernel</key>
		# 	<string>10.0.0</string>
		# 	<key>PlistPath</key>
		# 	<string>Contents/Info.plist</string>
		# </dict>

##################
# run
##################

# load config

root = minidom.parse('./EFI/OC/config.plist')

updateSMBIOS(root)
updateDeviceProperties(root)
updateKexts(root)

# load save

f = open('./EFI/OC/config.plist', 'w')
# f.write(root.toprettyxml(indent='    ', newl='\n'))
f.write(root.toxml())

# grab('hello')


