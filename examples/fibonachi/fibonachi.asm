IOVALUE:
    WORD 0

BEGIN:  ; input(len(username)
    IN          ; skip input buff length
    IN          ; how many numbers need to be calculated
    LD IOVALUE
    ST LEN
    POP

    IN          ; first number
    OUT
    LD IOVALUE
    IN          ; second number
    OUT
    LD IOVALUE
    ST BUFF
    CLA
LOOP:
    INC
    DUP
    LD LEN
    BGT
    JUMP END
    POP
    SWAP
    LD BUFF
    ADD
    ST IOVALUE
    OUT
    LD BUFF
    SWAP
    ST BUFF
    POP
    SWAP
    JUMP LOOP
END:
    HLT
LEN:
    WORD 10
BUFF:
    WORD 0