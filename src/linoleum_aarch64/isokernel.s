/*
 * Linux AArch64 Linoleum ABI bridge.
 * A=x19 B=x20 C=x21 D=x22 E=x23 X=x24 WS=x25.
 * The mapping and Apple-Silicon constraints were first investigated in PR #10
 * by Joris van de Donk; this implementation uses a checked full-width ABI.
 */

        .text
        .p2align 2
        .global isokernel
        .type isokernel, %function
isokernel:
        .cfi_startproc
        stp     x29, x30, [sp, #-16]!
        .cfi_def_cfa_offset 16
        .cfi_offset x29, -16
        .cfi_offset x30, -8
        mov     x29, sp
        bl      ISOKRNLCALL
        ldp     x29, x30, [sp], #16
        .cfi_restore x29
        .cfi_restore x30
        .cfi_def_cfa_offset 0

        /* RAMtop relocation may have replaced the mapping during the C call. */
        adrp    x9, pWorkspace
        ldr     x25, [x9, :lo12:pWorkspace]
        adrp    x9, isostatus
        ldr     w9, [x9, :lo12:isostatus]
        cbz     w9, .Lisokernel_done
        adrp    x9, FAIL
        ldr     w24, [x9, :lo12:FAIL]
        ret
.Lisokernel_done:
        adrp    x9, DONE
        ldr     w24, [x9, :lo12:DONE]
        ret
        .cfi_endproc
        .size isokernel, .-isokernel

        .p2align 2
        .global linoleum
        .type linoleum, %function
linoleum:
        .cfi_startproc
        sub     sp, sp, #80
        .cfi_def_cfa_offset 80
        stp     x19, x20, [sp, #0]
        .cfi_offset x19, -80
        .cfi_offset x20, -72
        stp     x21, x22, [sp, #16]
        .cfi_offset x21, -64
        .cfi_offset x22, -56
        stp     x23, x24, [sp, #32]
        .cfi_offset x23, -48
        .cfi_offset x24, -40
        str     x25, [sp, #48]
        .cfi_offset x25, -32
        stp     x29, x30, [sp, #64]
        .cfi_offset x29, -16
        .cfi_offset x30, -8
        mov     x29, sp

        adrp    x9, pWorkspace
        ldr     x25, [x9, :lo12:pWorkspace]
        mov     x19, xzr
        mov     x20, xzr
        mov     x21, xzr
        mov     x22, xzr
        mov     x23, xzr
        mov     x24, xzr
        adrp    x9, pCodeEntry
        ldr     x9, [x9, :lo12:pCodeEntry]
        blr     x9

        adrp    x9, aAtExit
        str     w19, [x9, :lo12:aAtExit]
        adrp    x9, bAtExit
        str     w20, [x9, :lo12:bAtExit]
        adrp    x9, cAtExit
        str     w21, [x9, :lo12:cAtExit]
        adrp    x9, dAtExit
        str     w22, [x9, :lo12:dAtExit]
        adrp    x9, eAtExit
        str     w23, [x9, :lo12:eAtExit]
        adrp    x9, xAtExit
        str     w24, [x9, :lo12:xAtExit]

        ldp     x29, x30, [sp, #64]
        .cfi_restore x29
        .cfi_restore x30
        ldr     x25, [sp, #48]
        .cfi_restore x25
        ldp     x23, x24, [sp, #32]
        .cfi_restore x23
        .cfi_restore x24
        ldp     x21, x22, [sp, #16]
        .cfi_restore x21
        .cfi_restore x22
        ldp     x19, x20, [sp, #0]
        .cfi_restore x19
        .cfi_restore x20
        add     sp, sp, #80
        .cfi_def_cfa_offset 0
        ret
        .cfi_endproc
        .size linoleum, .-linoleum

        .section .note.GNU-stack,"",%progbits
