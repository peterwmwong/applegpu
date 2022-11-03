import os
import sys
import applegpu

VERBOSE = False
STOP_ON_STOP = True

def disassemble(code):
	p = 0
	end = False
	skipping = False
	num_f16_ins = 0
	num_f32_ins = 0
	num_wait_ins = 0
	num_unknown_ins = 0
	num_ins = 0
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
		for o in applegpu.instruction_descriptors:
			if o.matches(n):
				length = o.decode_size(n)
				asm = o.disassemble(n, pc=p)
				mnem = asm.mnem
				if mnem == 'wait':
					num_wait_ins += 1
				elif mnem.startswith('f'):
					if mnem.endswith('32'):
						num_f32_ins += 1
					elif mnem.endswith('16'):
						num_f16_ins += 1
				asm_str = str(asm)
				if VERBOSE:
					asm_str = asm_str.ljust(60) + '\t'
					fields = '[' + ', '.join('%s=%r' % i for i in o.decode_fields(n)) + ']'
					rem = o.decode_remainder(n)
					if rem:
						fields = fields.ljust(85) + ' ' + str(rem)
					asm_str += fields
				print(asm_str)
				if mnem == 'stop':
					if STOP_ON_STOP:
						end = True
				break
		else:
			print('  <Disassembly Failed: address 0x%x' % p, 'instruction 0x%s>' % code[p:p+2].hex())
			num_unknown_ins += 1

		assert length >= 2 and length % 2 == 0
		p += length
	
	# TODO: Determine register usage count

	# Print stats to stderr
	if num_wait_ins > 0:
		print('    wait ', num_wait_ins, file=sys.stderr)
	if num_f32_ins > 0:
		print('    f32  ', num_f32_ins, file=sys.stderr)
	if num_f16_ins > 0:
		print('    f16  ', num_f16_ins, file=sys.stderr)
	if num_unknown_ins > 0:
		print('    unkn ', num_unknown_ins, file=sys.stderr)

if __name__ == '__main__':
	if len(sys.argv) > 1:
		f = open(sys.argv[1], 'rb')
		if len(sys.argv) > 2:
			f.seek(int(sys.argv[2], 0))
		code = f.read()
		disassemble(code)
	else:
		print('usage: python3 disassemble.py [filename] [offset]')
		exit(1)
