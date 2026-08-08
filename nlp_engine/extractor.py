import re
import csv
import os

class SkillExtractor:
    def __init__(self, skills_csv_path=None):
        self.skills_dict = {}  # alias -> normalized_name
        self.skill_categories = {}  # normalized_name -> category
        
        # Default path
        if not skills_csv_path:
            # Fallback path relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            skills_csv_path = os.path.join(current_dir, '..', 'data', 'skills.csv')
            
        self.load_skills_from_csv(skills_csv_path)

    def load_skills_from_csv(self, file_path):
        """
        Loads skills and aliases from a CSV file.
        """
        if not os.path.exists(file_path):
            return
            
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row['skill_name'].strip()
                cat = row['category'].strip()
                self.skill_categories[name] = cat
                
                # Add the normalized name itself as a key
                self.skills_dict[name.lower()] = name
                
                # Add aliases
                aliases_str = row.get('aliases', '')
                if aliases_str:
                    aliases = [a.strip() for a in aliases_str.split('|') if a.strip()]
                    for alias in aliases:
                        self.skills_dict[alias.lower()] = name

        # Sort keys by length descending to match longer strings first
        # (e.g. "Google Analytics" matches before "Google")
        self.sorted_aliases = sorted(self.skills_dict.keys(), key=len, reverse=True)

    def extract_skills(self, text):
        """
        Extracts skills from text using custom boundaries.
        Returns a dictionary of {normalized_name: matched_text}.
        """
        if not text:
            return {}
            
        text_lower = text.lower()
        extracted = {}
        
        # Custom boundary pattern: starts/ends with start/end of string or non-alphanumeric (excluding # and + and . for things like C++, C#, .NET, Vue.js)
        # Note: we need to be careful. Let's write boundary checks:
        # Preceded by start of string or non-(alphanumeric or # or + or .)
        # Followed by end of string or non-(alphanumeric or # or + or .)
        
        for alias in self.sorted_aliases:
            # Skip very short aliases that might cause false positives if not bounded properly
            if len(alias) <= 1:
                continue
                
            # Construct a regex that checks boundaries without using \b which fails on C++, C#, .NET
            # We escape the alias for regex
            escaped = re.escape(alias)
            
            # Left boundary: not preceded by alphanumeric, '#', '+', or '.'
            # Right boundary: not followed by alphanumeric, '#', '+', or '.'
            pattern = r'(?<![a-zA-Z0-9#+.])' + escaped + r'(?![a-zA-Z0-9#+.])'
            
            matches = re.finditer(pattern, text_lower)
            has_match = False
            for match in matches:
                has_match = True
                # Get the actual matched text from raw text
                start, end = match.span()
                raw_match = text[start:end]
                normalized_name = self.skills_dict[alias]
                
                if normalized_name not in extracted:
                    extracted[normalized_name] = raw_match
            
            # If matched, we can optionally remove it from the search text to prevent double matches,
            # but usually it's fine since we map to normalized names.
            # To avoid nested matches (e.g. "React" inside "ReactJS"), since we sort by length descending,
            # if we match "ReactJS" first, we can replace it with spaces in search text.
            if has_match:
                # Replace the matched parts with spaces of equal length to avoid sub-string matching later
                # We use a helper regex replacement
                text_lower = re.sub(pattern, ' ' * len(alias), text_lower)
                
        return extracted

    def get_category(self, skill_name):
        return self.skill_categories.get(skill_name, 'Other')
