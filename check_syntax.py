with open('static/app.js', 'r', encoding='utf-8') as f:
    content = f.read()

stack = []
pairs = {')': '(', '}': '{', ']': '['}
lines = content.split('\n')
in_block_comment = False

for line_no, line in enumerate(lines, 1):
    in_str = None
    escaped = False
    i = 0
    while i < len(line):
        ch = line[i]
        if in_block_comment:
            if line[i:i+2] == '*/':
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if in_str:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == in_str:
                in_str = None
            i += 1
            continue

        if line[i:i+2] == '/*':
            in_block_comment = True
            i += 2
            continue
        if line[i:i+2] == '//':
            break

        if ch in ('"', "'", '`'):
            in_str = ch
        elif ch in ('(', '{', '['):
            stack.append((ch, line_no))
        elif ch in (')', '}', ']'):
            if not stack:
                print(f'Unmatched {ch} at line {line_no}')
                exit(1)
            top, top_l = stack.pop()
            if top != pairs[ch]:
                print(f'Mismatched {ch} at line {line_no}, expected matching for {top} at line {top_l}')
                exit(1)
        i += 1

if stack:
    print(f'Unclosed delimiters remaining: {len(stack)}, first: {stack[0]}')
    exit(1)
print('ALL PARENTHESES, BRACES, AND BRACKETS ARE 100% BALANCED!')
