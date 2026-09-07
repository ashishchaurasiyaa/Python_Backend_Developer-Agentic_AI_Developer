import logging as log
log.basicConfig(level=log.INFO)
logger = log.getLogger(__name__)
s = "]"
stacks = []
is_mapping = {")":"(", "}":"{", "]":"["}
logger.info(f"Input string: {s}")

for i in s:
    log.info(f"Loop in : '{i}'")
    if i in is_mapping:
        log.info(f"get closing bracket: '{i}' | Stack top: '{stacks[-1] if stacks else 'EMPTY'}' ")
        if stacks and stacks[-1] == is_mapping[i]:
            stacks.pop()
            logger.info(f"Matched  after stack pop: {stacks}")
        else:
            logger.info(f"Not matched -> Invaild!")
            print(False)
            break
    else:
        stacks.append(i)
        logger.info(f"Opening bracket push: '{i}' | Stack: {stacks}")
result = stacks == []
logger.info(f"Final Stack is: {stacks} | Result: {result}")
print(result)


def isValid(self, s: str) -> bool:
    stack = []
    is_mapping = {")":"(","}":"{","]":"["}
    for i in s:
        if i in is_mapping:
            if stack and stack[-1] == is_mapping[i]:
                stack.pop()
            else:
                return False
        else:
            stack.append(i)
    return stack == []