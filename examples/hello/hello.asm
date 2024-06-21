IOVALUE:
    WORD 0

BEGIN:
    LD #MSG
    ST PTR
    POP
LOOP:
    INC
    LD LEN
    SWAP
    BLT     ; прошли заданное количество символов?
    JUMP END
    DUP
    LD [PTR]+
    ST IOVALUE
    OUT
    POP
    POP
    JUMP LOOP
END:
    HLT

PTR:
    WORD 0
LEN:
    WORD 11
MSG:
    WORD 72
    WORD 101
    WORD 108
    WORD 108
    WORD 111
    WORD 32
    WORD 119
    WORD 111
    WORD 114
    WORD 108
    WORD 100

