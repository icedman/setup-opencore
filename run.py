#!/usr/bin/python3

import json
import os
import subprocess
import sys
import re 

from xml.dom import minidom

# declare
config = {}
sources = {}
targets = {}
ocsanity = []
ocstree = {}

# settings
tab = '  '

def _log(t):
	print(t)

def _error(t):
	print('Error: ' + t)

def _header(head):
	if head:
		print('\n+----------------')
		print('|:: ' + head)
		print('+----------------')

def grab (prompt):
	sys.stdout.write(prompt + ' ')
	sys.stdout.flush()
	i = sys.stdin.readline().strip()
	return i

def clean() :
	subprocess.call(['rm', '-rf', './EFI'])
	subprocess.call(['rm', '-rf', './tools'])
	subprocess.call(['rm', '-rf', './kexts'])
 
def download(url, file, info):
	sx = os.path.splitext(file)
	filename = sx[0]
	extension = sx[1]

	if not os.path.isfile(file) and extension == '.zip':
		_log(tab + 'downloading ' + filename + '...')
		subprocess.call(['wget', '-P', os.path.dirname(file), url])

	if not os.path.isdir(file) and extension == '':
		os.chdir(os.path.dirname(file))
		_log(tab + 'cloning ' + filename + '...')
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

	if not os.path.isfile('./config.json'):
		f = open('./config.json', 'w')
		f.write('{}')
		f.close()

	downloadTools()
	downloadKexts()

	_log('\nPrepare done.')

	return True

def downloadTools ():
	for t in sources['tools']:
		target = os.path.join('./tools', os.path.basename(t['url']))
		download(t['url'], target, t)

	# apply our patches
	subprocess.call(['patch', '-fs', './tools/GenSMBIOS/GenSMBIOS.command', './support/genbios.patch'])
	
def downloadKexts ():
	for t in sources['kexts']:
		target = os.path.join('./kexts', os.path.basename(t['url']))
		download(t['url'], target, t)

def prepareBaseEFI ():
	subprocess.call(['cp',  '-R', './tools/opencore/X64/EFI', './'])
	subprocess.call(['cp',  './tools/opencore/Docs/Sample.plist', './EFI/OC/config.plist'])
	_log('base EFI copied')


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
		_error('smbios.json config not found. Run ./tool/GenSMBIOS/GenSMBIOS.command\n')
		return

	smbios = json.load(open('./smbios.json'))

	d = root.documentElement.getElementsByTagName('dict')[0]
	pi = findByChildKey(d, 'PlatformInfo')
	gen = findByChildKey(pi, 'Generic')

	_log('\nPlatformInfo:')

	for k in smbios:
		mod = findByChildKey(gen, k)
		mod.firstChild.nodeValue = smbios[k]
		_log(tab + k + ': ' + smbios[k])


def updateDeviceProperties(root):
	d = root.documentElement.getElementsByTagName('dict')[0]
	dev = findByChildKey(d, 'DeviceProperties')
	add = findByChildKey(dev, 'Add')

	if not os.path.isfile('./gpu.json'):
		_error('gpu.json config not found. Copy sample from /docs\n')
		return

	# gpu
	gpuAdd = 'PciRoot(0x0)/Pci(0x2,0x0)'
	_log('\nDeviceProperties: ' + gpuAdd)

	gpu = findByChildKey(add, gpuAdd)
	if not gpu:
		gpu = root.createElement('key')
		gpu.appendChild(root.createTextNode(gpuAdd))
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

		_log(tab + k + ': ' + value)

def updateKexts (root):
	subprocess.call(['rm', '-rf', './EFI/OC/Kexts/*' ])

	_log('\nKernel')

	if not os.path.isfile('./kexts.json'):
		_error('kexts.json config not found. Copy sample from /docs\n')
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

		if entry:
			parent = entry.parentNode
			enabled = findByChildKey(entry.parentNode, 'Enabled')
			enabled.tagName = 'true'
			_log(tab + kextName + ' enabled')
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
			_log(tab + kextName + ' added')

def updateACPI(root):
	# _log('\nACPI:')
	return

def cleanupConfig(root):
	# remove warnings
	for i in [1,2,3,4]:
		key = findByKey(root, '#WARNING - ' + str(i))
		if key:
			val = key.nextSibling.nextSibling
			key.parentNode.removeChild(val)
			key.parentNode.removeChild(key)

def lintXML():
	_log('\nLinting config.plist...')
	# prettify
	f = open('./config.plist', 'w')
	proc = subprocess.Popen(['xmllint --pretty 1 ./EFI/OC/config.plist'], shell=True, stdout=f)
	proc.wait()
	f.close()

	subprocess.call(['mv', './config.plist', './EFI/OC/config.plist'])

def save(root):
	f = open('./EFI/OC/config.plist', 'w')
	f.write(root.toxml())
	lintXML()

def menu(title, prompt, menu):
	_header(title)
	i = 1

	for m in menu:
		print(' ' + str(i) + '. ' + m['title'])
		i += 1

	res = grab('\n' + prompt)

	if not res:
		return True

	m = re.match('([0-9]*)', res)
	if m:
		res = m.groups()[0]
	else:
		return True

	if not res:
		return True

	res = int(res) - 1
	if res < len(menu):

		cmd = menu[int(res)]
		if cmd and 'cmd' in cmd:
			if cmd['cmd']():
				grab('press [enter] to continue...')
				print('\n')
				return True
			else:
				return False

		if cmd and 'return' in cmd:
			return cmd['return']


	return True

def quit():
	return False

def selectPlatform():
	_header('Platforms')

	mnu = []

	pc = menu(None, 'Select', [
		{ 'title': 'Laptop', 'return': 'laptop'},
		{ 'title': 'Desktop', 'return': 'desktop'}
	])

	target = './tools/OCSanity/rules'
	if not os.path.isdir(target):
		_error('OCSanity not available')

	for f in os.listdir(target):
		m = re.match('([a-zA-Z]{1,20})[0-9]{0,3}', f)
		if m:
			g = m.groups()[0]
			targets[g] = {
				'name': g.replace('laptop', 'laptop '),
				'path': os.path.join(target, f),
				'laptop': 'laptop' in g
				}

	for t in targets:
		f = open(targets[t]['path'])
		targets[t]['description'] = f.readline().strip().replace('# ', '')
		f.close()

		if targets[t]['laptop'] and not pc == 'laptop':
			continue

		if not targets[t]['laptop'] and pc == 'laptop':
			continue

		# print(targets[t]['description'])
		mnu.append({
			'title': targets[t]['description'],
			'return': t
			})

	res = menu('Generation', 'Select', mnu)
	if res == True:
		return True

	subprocess.call(['cp', targets[res]['path'], './ocsanity.lst'])
	_log(targets[res]['description'] + ' selected')
	
	return True

def build():
	root = minidom.parse('./EFI/OC/config.plist')

	updateSMBIOS(root)
	updateDeviceProperties(root)
	updateKexts(root)
	updateACPI(root)
	applyOCS(root, ocstree)
	cleanupConfig(root)
	save(root)

	_log('\nBuild Done.')

	return True

def loadOCSanity():
	if not os.path.isfile('./ocsanity.lst'):
		_error('Platform yet not selected.')
		return

	f = open('./ocsanity.lst', 'r')
	res = f.readlines()
	f.close()

	return res

def buildOCSTree():
	tree = {}
	stack = []
	topLevel = False
	wasNL = True
	sublevel = False
	for l in ocsanity:
		if l.startswith('#') or l.startswith('='):
			continue

		if len(l.strip()) == 0:
			if sublevel:
				stack.pop()
				sublevel = False
			continue

		if len(stack) == 0:
			stack = [tree]

		top = stack[len(stack)-1]

		# item
		if l.startswith(' '):
			if not '_items' in top:
				top['_items'] = []
			top['_items'].append(l.strip())
			continue

		if l.startswith(':'):
			sublevel = True
		else:
			top = tree
			sublevel = False

		l = l.strip().replace(':', '')
		top[l] = {}
		stack.append(top[l])

	f = open('./ocsanity.json', 'w')
	json.dump(tree, f, indent=4)
	f.close()

	return tree

def applyOCSItem(relative, item):
	d = relative #.getElementsByTagName('dict')[0]
	m = re.match('([a-zA-Z0-9]*)=(yes|no)', item)
	if m:
		g = m.groups()
		sitem = findByChildKey(d, g[0])
		if not sitem:
			return

		ntag = 'false'
		if g[1] == 'yes':
			ntag = 'true'
		if ntag != sitem.tagName:
			sitem.tagName = ntag
			_log(tab + tab + g[0] + ' set to ' + ntag)

def _applyOCS(relative, ocst, t):
	dd = relative.getElementsByTagName('dict')
	if len(dd) == 0:
		dd = relative.getElementsByTagName('array')
	if len(dd) == 0:
		d = relative
	else:
		d = dd[0]

	if not t:
		t = tab

	for k in ocst:
		if k.startswith('_'):
			if k == '_items' :
				for i in ocst['_items']:
					# _log(t + tab + i)
					applyOCSItem(d, i)

			continue

		_log(t + k)

		r = findByChildKey(d, k)
		if not r:
			r = findByChildKey(relative, k)

		if not r:
			print('skip ' + k)
			continue

		_applyOCS(r, ocst[k], t + tab)

def applyOCS(root,ocst):
	_log('\napplying OCSanity settings')
	_applyOCS(root,ocst,'')

##################
# run
##################

_log('Checking files')

sources = json.load(open('./sources.json'))

if not os.path.isdir('./EFI'):
	prepare()
	prepareBaseEFI()

ocsanity = loadOCSanity()
ocstree = buildOCSTree()

# print(ocstree)

def run():
	running = True
	while(running):
		running = menu('Main', 'select:', [
				{ 'title': 'Prepare tools', 'cmd': prepare },
				{ 'title': 'Select platform', 'cmd': selectPlatform },
				{ 'title': 'Configure', 'cmd': quit },
				{ 'title': 'Build EFI', 'cmd': build },
				{ 'title': 'Quit', 'cmd': quit },
		])

run()
