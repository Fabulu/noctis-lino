/*
 *	linoleum_linux64 Linoleum Run-Time Module for linux aarch64 systems
 *
 *	AArch64 (AAPCS64) port.
 *	L.IN.OLEUM register map on AArch64 (x19..x25 are callee-saved, so the
 *	C isokernel preserves them automatically):
 *	  A=x19 B=x20 C=x21 D=x22 E=x23 X=x24 WS=x25
 *	Scratch: x9..x18, x0..x8 (ABI).
 */

	.text
	.globl isokernel
	.type isokernel, %function
isokernel:
	/* keep a record of the A..E registers in the exit globals */
	adrp	x9, aAtExit
	str	w19, [x9, #:lo12:aAtExit]
	str	w20, [x9, #:lo12:bAtExit]
	str	w21, [x9, #:lo12:cAtExit]
	str	w22, [x9, #:lo12:dAtExit]
	str	w23, [x9, #:lo12:eAtExit]
	/* preserve frame + link, keep the stack 16-byte aligned */
	stp	x29, x30, [sp, #-16]!
	mov	x29, sp
	bl	ISOKRNLCALL
	ldp	x29, x30, [sp], #16
	/* X = FAIL or DONE depending on isostatus */
	adrp	x9, isostatus
	ldr	w9, [x9, #:lo12:isostatus]
	cbz	w9, .Lisokernel_done
	adrp	x24, FAIL
	ldr	w24, [x24, #:lo12:FAIL]
	ret
.Lisokernel_done:
	adrp	x24, DONE
	ldr	w24, [x24, #:lo12:DONE]
	ret
	.size isokernel, . - isokernel


	.text
	.globl linoleum
	.type linoleum, %function
linoleum:
	/* save the game registers + frame; keep 16-byte alignment */
	stp	x19, x20, [sp, #-16]!
	stp	x21, x22, [sp, #-16]!
	stp	x23, x24, [sp, #-16]!
	stp	x25, x29, [sp, #-16]!
	mov	x29, sp
	adrp	x9, sAtEntry
	mov	x10, sp
	str	x10, [x9, #:lo12:sAtEntry]
	/* WS = pWorkspace */
	adrp	x9, pWorkspace
	ldr	x25, [x9, #:lo12:pWorkspace]
	/* zero A..E and X */
	mov	w19, wzr
	mov	w20, wzr
	mov	w21, wzr
	mov	w22, wzr
	mov	w23, wzr
	mov	w24, wzr
	/* call the application entry point */
	adrp	x9, pCodeEntry
	ldr	x9, [x9, #:lo12:pCodeEntry]
	blr	x9
	/* record the exit registers */
	adrp	x9, aAtExit
	str	w19, [x9, #:lo12:aAtExit]
	str	w20, [x9, #:lo12:bAtExit]
	str	w21, [x9, #:lo12:cAtExit]
	str	w22, [x9, #:lo12:dAtExit]
	str	w23, [x9, #:lo12:eAtExit]
	str	w24, [x9, #:lo12:xAtExit]
	/* restore */
	ldp	x25, x29, [sp], #16
	ldp	x23, x24, [sp], #16
	ldp	x21, x22, [sp], #16
	ldp	x19, x20, [sp], #16
	ret
	.size linoleum, . - linoleum
