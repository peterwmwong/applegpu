import os
import sys
import applegpu

VERBOSE = False
STOP_ON_STOP = True

def disassemble(code):
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
	print('    {:16} {:4}'.format('TOTAL', sum(ins_counts.values())), file=sys.stderr)
	print('    ---------------------', file=sys.stderr)
	for key, value in sorted(ins_counts.items()):
		print('    {:16} {:4}'.format(key, value), file=sys.stderr)

def pairwise(iterable):
    "s -> (s0, s1), (s2, s3), (s4, s5), ..."
    a = iter(iterable)
    return zip(a, a)

if __name__ == '__main__':
	if len(sys.argv) > 2:
		code = open(sys.argv[1], 'rb').read()
		for fn_name,offset in pairwise(sys.argv[2:]):
			print('', file=sys.stderr)
			print(fn_name, file=sys.stderr)
			
			print('')
			print('-' * len(fn_name))
			print(fn_name)
			print('-' * len(fn_name))
			disassemble(code[int(offset, 0):])
	else:
		print('usage: python3 disassemble.py [filename] [[function_name] [offset]]...')
		exit(1)
