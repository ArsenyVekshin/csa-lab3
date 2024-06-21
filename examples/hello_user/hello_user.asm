IOVALUE:
    WORD 0

BEGIN:  ; input(len(username)
    IN
    LD IOVALUE
    ST USERLEN
    POP
    LD #USERMSG
    ST PTR
    POP

INPUTLOOP:  ; input(username)
    INC
    LD USERLEN
    SWAP
    BLT     ; прошли заданное количество символов?
    JUMP OUTPUT1
    IN
    LD IOVALUE
    ST [PTR]+
    POP
    JUMP INPUTLOOP

OUTPUT1:
    CLA
    LD #HELLOMSG
    ST PTR
    POP
OUTPUTLOOP1:
    INC
    LD HELLOLEN
    SWAP
    BLT     ; прошли заданное количество символов?
    JUMP OUTPUT2
    DUP
    LD [PTR]+
    ST IOVALUE
    OUT
    POP
    POP
    JUMP OUTPUTLOOP1

OUTPUT2:
    CLA
    LD #USERMSG
    ST PTR
    POP
OUTPUTLOOP2:
    INC
    LD USERLEN
    SWAP
    BLT     ; прошли заданное количество символов?
    JUMP END
    DUP
    LD [PTR]+
    ST IOVALUE
    OUT
    POP
    POP
    JUMP OUTPUTLOOP2

END:
    LD #33
    ST IOVALUE
    OUT
    HLT

PTR:
    WORD 0
HELLOLEN:
    WORD 7
HELLOMSG:
    WORD 72
    WORD 101
    WORD 108
    WORD 108
    WORD 111
    WORD 44
    WORD 32
USERLEN:
    WORD 0
USERMSG:
    WORD 0