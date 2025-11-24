import re

def distinguished_to_canonical(distinguished_name):
    if not distinguished_name:
        return None
    
    # Split the distinguished name into components
    components = re.split(r',(?![^\[]*\])', distinguished_name)
    
    # Initialize the parts of the canonical name
    dc_parts = []
    ou_parts = []
    cn_part = None
    
    # Process each component
    for component in components:
        key, value = component.split('=')
        if key == 'DC':
            dc_parts.append(value)
        elif key == 'OU':
            ou_parts.insert(0, value)  # Reverse order for OU parts
        elif key == 'CN':
            cn_part = value
    
    # Join the parts to form the canonical name
    domain = '.'.join(dc_parts)
    path = '/'.join(ou_parts)
    canonical_name = f'{domain}/{path}/{cn_part}'
    
    return canonical_name



def run():
    # Example usage
    distinguished_name = 'CN=AIT-ADM-employees-29619,OU=SecurityGroups,OU=AIT,OU=DTUBasen,DC=win,DC=dtu,DC=dk'
    canonical_name = distinguished_to_canonical(distinguished_name)
    print(canonical_name)  # Output: win.dtu.dk/DTUBasen/AIT/SecurityGroups/AIT-ADM-employees-29619


# if main 
if __name__ == "__main__":
    run()
