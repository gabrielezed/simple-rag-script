# modules/file_processor.py

import os
from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

def get_ignore_patterns(ignore_file_path, root_dir):
    """
    Carica le regole di esclusione da un file .ragignore e aggiunge quelle di default.
    """
    # Patterns di default per escludere file non necessari
    default_patterns = [
        '.git/',
        '.gitignore',
        '*.db',
        '*.db-journal',
        '__pycache__/',
        os.path.basename(root_dir) + "/" + os.path.basename(ignore_file_path) # Esclude se stesso
    ]
    
    patterns = default_patterns
    full_ignore_path = os.path.join(root_dir, ignore_file_path)

    if os.path.exists(full_ignore_path):
        with open(full_ignore_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    patterns.append(line)
    
    # Usa GitWildMatchPattern per la compatibilità con lo stile .gitignore
    return PathSpec.from_lines(GitWildMatchPattern, patterns)

def load_files_to_index(root_dir, ignore_spec):
    """
    Scansiona ricorsivamente una directory e restituisce i percorsi dei file
    che non sono esclusi dalle regole.
    """
    for root, _, files in os.walk(root_dir):
        for file in files:
            file_path = os.path.join(root, file)
            # Normalizza il percorso per un matching corretto rispetto alla root
            relative_path = os.path.relpath(file_path, os.path.dirname(root_dir))
            
            if not ignore_spec.match_file(relative_path):
                yield file_path