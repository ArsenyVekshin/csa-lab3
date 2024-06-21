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
    JUMP END
    IN
    LD IOVALUE
    ST [PTR]+
    POP
    JUMP INPUTLOOP

END:
    HLT

PTR:
    WORD 0
USERLEN:
    WORD 0
USERMSG:
    WORD 0