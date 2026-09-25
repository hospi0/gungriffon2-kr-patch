BIN_PATH = r"C:\claude\Terra Phantastica (Japan)\Terra Phantastica (Japan) (Track 1).bin"
LOAD_BASE = 0x06010000
FILE_LBA = 72

def read_0fbin(file_offset, size):
    data = bytearray()
    with open(BIN_PATH, 'rb') as f:
        sec_off = file_offset
        remaining = size
        while remaining > 0:
            lba = FILE_LBA + sec_off // 2048
            in_sec = sec_off % 2048
            f.seek(lba * 2352 + 16 + in_sec)
            to_read = min(remaining, 2048 - in_sec)
            data.extend(f.read(to_read))
            sec_off += to_read
            remaining -= to_read
    return bytes(data)

def disasm_sh2(code, base_addr, max_instr=400):
    lines = []
    i = 0
    while i < len(code) - 1 and len(lines) < max_instr:
        addr = base_addr + i
        w = (code[i] << 8) | code[i+1]
        i += 2
        n = (w >> 8) & 0xF
        m = (w >> 4) & 0xF
        d = w & 0xF
        imm8 = w & 0xFF
        imm8s = imm8 - 256 if imm8 >= 128 else imm8
        op = w >> 12

        if w == 0x0009: ins = "NOP"
        elif w == 0x000B: ins = "RTS"
        elif w == 0x002B: ins = "RTE"
        elif w == 0x0008: ins = "CLRT"
        elif op == 0:
            if (w & 0xF0FF) == 0x0029: ins = f"MOVT R{n}"
            elif (w & 0xF00F) == 0x000C: ins = f"MOV.B @R{m}, R{n}"
            elif (w & 0xF00F) == 0x000D: ins = f"MOV.W @R{m}, R{n}"
            elif (w & 0xF00F) == 0x000E: ins = f"MOV.L @R{m}, R{n}"
            elif (w & 0xF00F) == 0x0004: ins = f"MOV.B R{m}, @(R0,R{n})"
            elif (w & 0xF00F) == 0x0005: ins = f"MOV.W R{m}, @(R0,R{n})"
            elif (w & 0xF00F) == 0x0006: ins = f"MOV.L R{m}, @(R0,R{n})"
            elif (w & 0xF00F) == 0x000F: ins = f"MAC.L @R{m}+, @R{n}+"
            elif (w & 0xF0FF) == 0x000A: ins = f"STS MACH, R{n}"
            elif (w & 0xF0FF) == 0x001A: ins = f"STS MACL, R{n}"
            elif (w & 0xF0FF) == 0x002A: ins = f"STS PR, R{n}"
            elif (w & 0xF0FF) == 0x0023: ins = f"BRAF R{n}"
            elif (w & 0xF0FF) == 0x0003: ins = f"BSRF R{n}"
            elif (w & 0xFF) == 0x09: ins = "NOP"
            elif (w & 0xFF) == 0x0B: ins = "RTS"
            else: ins = f"? {w:04X}"
        elif op == 1: ins = f"MOV.L R{m}, @({d*4},R{n})"
        elif op == 2:
            s = d
            if s==0: ins=f"MOV.B R{m}, @R{n}"
            elif s==1: ins=f"MOV.W R{m}, @R{n}"
            elif s==2: ins=f"MOV.L R{m}, @R{n}"
            elif s==4: ins=f"MOV.B R{m}, @-R{n}"
            elif s==5: ins=f"MOV.W R{m}, @-R{n}"
            elif s==6: ins=f"MOV.L R{m}, @-R{n}"
            elif s==7: ins=f"DIV0S R{m}, R{n}"
            elif s==8: ins=f"TST R{m}, R{n}"
            elif s==9: ins=f"AND R{m}, R{n}"
            elif s==0xA: ins=f"XOR R{m}, R{n}"
            elif s==0xB: ins=f"OR R{m}, R{n}"
            elif s==0xC: ins=f"CMP/STR R{m}, R{n}"
            elif s==0xD: ins=f"XTRCT R{m}, R{n}"
            elif s==0xE: ins=f"MULU.W R{m}, R{n}"
            elif s==0xF: ins=f"MULS.W R{m}, R{n}"
            else: ins=f"? {w:04X}"
        elif op == 3:
            s = d
            if s==0: ins=f"CMP/EQ R{m}, R{n}"
            elif s==2: ins=f"CMP/HS R{m}, R{n}"
            elif s==3: ins=f"CMP/GE R{m}, R{n}"
            elif s==4: ins=f"DIV1 R{m}, R{n}"
            elif s==5: ins=f"DMULU.L R{m}, R{n}"
            elif s==6: ins=f"CMP/HI R{m}, R{n}"
            elif s==7: ins=f"CMP/GT R{m}, R{n}"
            elif s==8: ins=f"SUB R{m}, R{n}"
            elif s==0xA: ins=f"SUBC R{m}, R{n}"
            elif s==0xB: ins=f"SUBV R{m}, R{n}"
            elif s==0xC: ins=f"ADD R{m}, R{n}"
            elif s==0xD: ins=f"DMULS.L R{m}, R{n}"
            elif s==0xE: ins=f"ADDC R{m}, R{n}"
            elif s==0xF: ins=f"ADDV R{m}, R{n}"
            else: ins=f"? {w:04X}"
        elif op == 4:
            sub = w & 0xFF
            tbl = {0x00:f"SHLL R{n}",0x01:f"SHLR R{n}",0x02:f"STS.L MACH, @-R{n}",
                   0x04:f"ROTL R{n}",0x05:f"ROTR R{n}",0x06:f"LDS.L @R{n}+, MACH",
                   0x08:f"SHLL2 R{n}",0x09:f"SHLR2 R{n}",0x0A:f"LDS R{n}, MACH",
                   0x0B:f"JSR @R{n}",0x0E:f"LDC R{n}, SR",0x10:f"DT R{n}",
                   0x11:f"CMP/PZ R{n}",0x12:f"STS.L MACL, @-R{n}",0x15:f"CMP/PL R{n}",
                   0x16:f"LDS.L @R{n}+, MACL",0x18:f"SHLL8 R{n}",0x19:f"SHLR8 R{n}",
                   0x1A:f"LDS R{n}, MACL",0x1B:f"TAS.B @R{n}",
                   0x20:f"SHAL R{n}",0x21:f"SHAR R{n}",0x22:f"STS.L PR, @-R{n}",
                   0x24:f"ROTCL R{n}",0x25:f"ROTCR R{n}",0x26:f"LDS.L @R{n}+, PR",
                   0x28:f"SHLL16 R{n}",0x29:f"SHLR16 R{n}",0x2A:f"LDS R{n}, PR",
                   0x2B:f"JMP @R{n}",0x2E:f"LDC R{n}, VBR"}
            if sub in tbl: ins = tbl[sub]
            elif (w&0xF)==3: ins=f"NEG R{m}, R{n}"
            elif (w&0xF)==7: ins=f"NOT R{m}, R{n}"
            elif (w&0xF)==0xB: ins=f"NEGC R{m}, R{n}"
            elif (w&0xF)==0xF: ins=f"EXTS.W R{m}, R{n}"
            elif (w&0xF)==0xE: ins=f"EXTS.B R{m}, R{n}"
            elif (w&0xF)==0xC: ins=f"EXTU.B R{m}, R{n}"
            elif (w&0xF)==0xD: ins=f"EXTU.W R{m}, R{n}"
            else: ins=f"? {w:04X}"
        elif op == 5: ins = f"MOV.L @({d*4},R{m}), R{n}"
        elif op == 6:
            s = d
            if s==0: ins=f"MOV.B @R{m}, R{n}"
            elif s==1: ins=f"MOV.W @R{m}, R{n}"
            elif s==2: ins=f"MOV.L @R{m}, R{n}"
            elif s==3: ins=f"MOV R{m}, R{n}"
            elif s==4: ins=f"MOV.B @R{m}+, R{n}"
            elif s==5: ins=f"MOV.W @R{m}+, R{n}"
            elif s==6: ins=f"MOV.L @R{m}+, R{n}"
            elif s==7: ins=f"NOT R{m}, R{n}"
            elif s==8: ins=f"SWAP.B R{m}, R{n}"
            elif s==9: ins=f"SWAP.W R{m}, R{n}"
            elif s==0xA: ins=f"NEGC R{m}, R{n}"
            elif s==0xB: ins=f"NEG R{m}, R{n}"
            elif s==0xC: ins=f"EXTU.B R{m}, R{n}"
            elif s==0xD: ins=f"EXTU.W R{m}, R{n}"
            elif s==0xE: ins=f"EXTS.B R{m}, R{n}"
            elif s==0xF: ins=f"EXTS.W R{m}, R{n}"
            else: ins=f"? {w:04X}"
        elif op == 7: ins = f"ADD #0x{imm8:02X}, R{n}  ; {imm8s}"
        elif op == 8:
            sub = (w>>8)&0xF
            if sub==0: ins=f"MOV.B R0, @(0x{d:X},R{m})"
            elif sub==1: ins=f"MOV.W R0, @(0x{d*2:X},R{m})"
            elif sub==4: ins=f"MOV.B @(0x{d:X},R{m}), R0"
            elif sub==5: ins=f"MOV.W @(0x{d*2:X},R{m}), R0"
            elif sub==8: ins=f"CMP/EQ #0x{imm8:02X}, R0"
            elif sub==9:
                t=addr+4+imm8s*2; ins=f"BT 0x{t:08X}"
            elif sub==0xB:
                t=addr+4+imm8s*2; ins=f"BF 0x{t:08X}"
            elif sub==0xD:
                t=addr+4+imm8s*2; ins=f"BT/S 0x{t:08X}"
            elif sub==0xF:
                t=addr+4+imm8s*2; ins=f"BF/S 0x{t:08X}"
            else: ins=f"? {w:04X}"
        elif op==9:
            t=(addr+4)+imm8s*2; ins=f"MOV.W @(PC+{imm8s*2}), R{n}  ;@0x{t:08X}"
        elif op==0xA:
            d12=w&0xFFF; d12s=d12-4096 if d12>=2048 else d12
            t=(addr+4)+d12s*2; ins=f"BRA 0x{t:08X}"
        elif op==0xB:
            d12=w&0xFFF; d12s=d12-4096 if d12>=2048 else d12
            t=(addr+4)+d12s*2; ins=f"BSR 0x{t:08X}"
        elif op==0xC:
            sub=(w>>8)&0xF
            if sub==0: ins=f"MOV.B R0, @(0x{imm8:02X},GBR)"
            elif sub==1: ins=f"MOV.W R0, @(0x{imm8*2:02X},GBR)"
            elif sub==2: ins=f"MOV.L R0, @(0x{imm8*4:02X},GBR)"
            elif sub==3: ins=f"TRAPA #0x{imm8:02X}"
            elif sub==4: ins=f"MOV.B @(0x{imm8:02X},GBR), R0"
            elif sub==5: ins=f"MOV.W @(0x{imm8*2:02X},GBR), R0"
            elif sub==6: ins=f"MOV.L @(0x{imm8*4:02X},GBR), R0"
            elif sub==7: ins=f"MOVA @(0x{imm8*4:02X},PC), R0"
            elif sub==8: ins=f"TST #0x{imm8:02X}, R0"
            elif sub==9: ins=f"AND #0x{imm8:02X}, R0"
            elif sub==0xA: ins=f"XOR #0x{imm8:02X}, R0"
            elif sub==0xB: ins=f"OR #0x{imm8:02X}, R0"
            elif sub==0xC: ins=f"TST.B #0x{imm8:02X}, @(R0,GBR)"
            elif sub==0xD: ins=f"AND.B #0x{imm8:02X}, @(R0,GBR)"
            elif sub==0xE: ins=f"XOR.B #0x{imm8:02X}, @(R0,GBR)"
            elif sub==0xF: ins=f"OR.B #0x{imm8:02X}, @(R0,GBR)"
            else: ins=f"? {w:04X}"
        elif op==0xD:
            t=(addr+4&~3)+imm8*4; ins=f"MOV.L @(PC+{imm8*4}), R{n}  ;@0x{t:08X}"
        elif op==0xE:
            val=imm8 if imm8<128 else imm8-256
            ins=f"MOV #0x{imm8:02X}, R{n}  ; {val}"
        else: ins=f"? {w:04X}"

        lines.append((addr, w, ins))
    return lines
