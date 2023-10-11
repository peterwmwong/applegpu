import os
import sys
import applegpu
import re
import subprocess

VERBOSE = False
STOP_ON_STOP = True

def disassemble(code, shader_display_name):
	p = 0
	end = False
	skipping = False
	ins_counts = {}
	while p < len(code) and not end:
		n = applegpu.opcode_to_number(code[p:])
		if not skipping and (n & 0xFFFFffff) == 0:
			print()
			skipping = True
		if skipping:
			if (n & 0xFFFF) == 0:
				p += 2
				continue
			else:
				skipping = False
		length = 2
		ins_name = 'unkn'
		for o in applegpu.instruction_descriptors:
			if o.matches(n):
				length = o.decode_size(n)
				asm = o.disassemble(n, pc=p)
				ins_name = asm.ins_name
				asm_str = str(asm)
				if VERBOSE:
					asm_str = asm_str.ljust(60) + '\t'
					fields = '[' + ', '.join('%s=%r' % i for i in o.decode_fields(n)) + ']'
					rem = o.decode_remainder(n)
					if rem:
						fields = fields.ljust(85) + ' ' + str(rem)
					asm_str += fields
				# print('0x%X:' % p, asm_str)
				# TODO(0): Parse out registers
				# - Either dig through the asm.operands or regex it (`(\b|_)r[0-9][0-9]?`)
				print(asm_str)
				if ins_name == 'stop':
					if STOP_ON_STOP:
						end = True
				break
		else:
			print('0x%4X:' % p, code[p:p+2].hex().ljust(20), '<disassembly failed>')
		
		ins_counts[ins_name] = ins_counts.get(ins_name, 0) + 1

		assert length >= 2 and length % 2 == 0
		p += length
	
	# TODO(1): Display Branch Target labeling
	# TODO(1): Determine register usage count
	
	# Print stats to stderr
	print(shader_display_name, file=sys.stderr)
	print('    {:16} {:4}'.format('TOTAL', sum(ins_counts.values())), file=sys.stderr)
	print('    ---------------------', file=sys.stderr)
	for key, value in sorted(ins_counts.items()):
		print('    {:16} {:4}'.format(key, value), file=sys.stderr)
	print(file=sys.stderr)

TMP_PATH = '/tmp/metal-applegpu-disasm__tmp.bin'
TMP_GPU_LD_MD_PATH = '/tmp/metal-applegpu-disasm__tmp-gpu-ld-md.bin'
MAGIC_BYTES_PREFIX = b'\xcf\xfa\xed\xfe'

if __name__ == '__main__':
	with open(sys.argv[1], 'rb') as inf:
		data = inf.read()

	for i in re.finditer(MAGIC_BYTES_PREFIX, data):
		current = data[i.start():]
		with open(TMP_PATH, 'wb') as outf:
			outf.write(current)

		shader_name = ''
		shader_type = ''
		code = None
		for i in re.finditer('Section\n  sectname (.*)\n   segname (.*)\n      addr .*\n      size (.*)\n    offset (.*)',
							subprocess.check_output(f'otool -l {TMP_PATH}', shell=True).decode('ascii')):
			sectname, segname, size, offset = i.groups()
			size = int(size, 16)
			offset = int(offset)
			if segname == '__GPU_LD_MD':
				with open(TMP_GPU_LD_MD_PATH, 'wb') as f:
					f.write(current[offset:offset+size])
				strings_result = subprocess.check_output(f'strings {TMP_GPU_LD_MD_PATH}', shell=True).decode('ascii').strip().split()
				strings_result.reverse()
				shader_type, shader_name = strings_result[0:2]
				if shader_type not in ['compute', 'fragment', 'vertex', 'object', 'mesh']:
					print(f"ERROR: Could not find shader name with a supported type within...\n{strings_result}")
					continue
			if sectname == '__text':
				code = current[offset:offset+size]

		if code:
			if code.startswith(MAGIC_BYTES_PREFIX):
				continue
			if code.startswith(b'MTLPSBIN'):
				continue
			for line in subprocess.check_output(['nm', TMP_PATH]).decode('ascii').strip().split('\n'):
				a, b, c = line.split()
				if 'ltmp' not in c:
					shader_display_name = f'[[{shader_type}]] {shader_name}'
					shader_name_postfix = c.removeprefix('_agc.main').removeprefix('.')
					if shader_name_postfix != '':
						shader_display_name +=  f' ({shader_name_postfix})'
					print('\n' + '-' * len(shader_display_name))
					print(shader_display_name)
					print('-' * len(shader_display_name))
					disassemble(code[int(a,16):], shader_display_name) # relies on STOP_ON_STOP

	for path in [TMP_PATH, TMP_GPU_LD_MD_PATH]:
		try:
			os.remove(path)
		except FileNotFoundError:
			pass
