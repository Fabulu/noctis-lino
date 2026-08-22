/*
 *	linoleum_macos64 Linoleum Run-Time Module for macOS 64-bit systems
 *	Copyright (C) 2004-2006 Peterpaul Klein Haneveld
 *
 *	x86_64 SysV ABI port, Mach-O (Mac OS X / macOS) variant.
 *	Mach-O C symbols carry a leading underscore.
 *	L.IN.OLEUM register map on x86_64:
 *	  A=rax  B=rbx  C=rcx  D=rdx  E=rsi  X=rbp  WS=rdi
 */

	.text
	.globl _isokernel
_isokernel:
	/* keep a record of the A..E registers in the exit globals */
	movl	%eax, _aAtExit(%rip)
	movl	%ebx, _bAtExit(%rip)
	movl	%ecx, _cAtExit(%rip)
	movl	%edx, _dAtExit(%rip)
	movl	%esi, _eAtExit(%rip)
	/* preserve caller-saved L.IN.OLEUM registers across the C call,
	 * aligning the stack to 16 bytes for the SysV ABI */
	pushq	%rbp
	movq	%rsp, %rbp
	subq	$48, %rsp
	movq	%rax, -16(%rbp)
	movq	%rcx, -24(%rbp)
	movq	%rdx, -32(%rbp)
	movq	%rsi, -40(%rbp)
	movq	%rdi, -48(%rbp)
	andq	$-16, %rsp
	call	_ISOKRNLCALL
	/* C callees should preserve x87 control state, but make the Lino
	 * boundary explicit rather than inheriting host-library behaviour. */
	fldcw	L_lino_fcw(%rip)
	movq	-16(%rbp), %rax
	movq	-24(%rbp), %rcx
	movq	-32(%rbp), %rdx
	movq	-40(%rbp), %rsi
	movq	-48(%rbp), %rdi
	movq	%rbp, %rsp
	popq	%rbp
	movq	_pWorkspace(%rip), %rdi
	cmpl	$0, _isostatus(%rip)
	je	L_isokernel_end
	movl	_FAIL(%rip), %ebp
	jmp	L_isokernel_exit
L_isokernel_end:
	movl	_DONE(%rip), %ebp
L_isokernel_exit:
	ret


	.text
	.globl _linoleum
_linoleum:
	pushq	%rbp
	pushq	%rbx
	pushq	%rsi
	pushq	%rdi
	movq	%rsp, _sAtEntry(%rip)
	movq	_pWorkspace(%rip), %rdi
	xorl	%eax, %eax
	xorl	%ebx, %ebx
	xorl	%ecx, %ecx
	xorl	%edx, %edx
	xorl	%esi, %esi
	xorl	%ebp, %ebp
	movq	_pCodeEntry(%rip), %rax
	/* The production Lino contract is PC=64, nearest-even, masked. */
	fldcw	L_lino_fcw(%rip)
	call	*%rax
	movl	%eax, _aAtExit(%rip)
	movl	%ebx, _bAtExit(%rip)
	movl	%ecx, _cAtExit(%rip)
	movl	%edx, _dAtExit(%rip)
	movl	%esi, _eAtExit(%rip)
	movl	%ebp, _xAtExit(%rip)
	movq	_sAtEntry(%rip), %rsp
	popq	%rdi
	popq	%rsi
	popq	%rbx
	popq	%rbp
	ret


	.section __TEXT,__const
	.p2align 1
L_lino_fcw:
	.short	0x133f
