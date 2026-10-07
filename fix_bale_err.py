def fix_bale_unbound_error():
    with open('platforms/bale_adapter.py', 'r', encoding='utf-8') as f:
        lines = f.read().split('\n')
        
    for i, line in enumerate(lines):
        if 'await bale.send_message(' in line and 'chat_id' in lines[i+1] and 'if media_type ==' in lines[i+2]:
            # This is the line where the message is sent
            lines[i] = line.replace('await bale.send_message(', 'status_msg_res = await bale.send_message(')
            lines.insert(i+5, ' '*40 + 'status_msg_id = status_msg_res.get("result", {}).get("message_id") if isinstance(status_msg_res, dict) else None')
            break
            
    for i in range(len(lines)):
        if 'status_msg.id' in lines[i]:
            lines[i] = lines[i].replace('status_msg.id', 'status_msg_id')
            
    with open('platforms/bale_adapter.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

fix_bale_unbound_error()
