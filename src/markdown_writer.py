"""
Markdown writer for Greek Room repeated words analysis.
Refactored from write_to_html in repeated_words.py
"""
import datetime
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional
import regex


def write_to_markdown(feedback: list, misc_data_dict: dict, corpus, markdown_out_filename: str,
                      lang_code: str, lang_name: Optional[str] = None, 
                      project_id: Optional[str] = None) -> None:
    """
    Write repeated words analysis results to a Markdown file.
    
    Args:
        feedback: List of feedback dictionaries containing repeated word information
        misc_data_dict: Dictionary containing legitimate duplicate data
        corpus: Corpus object containing sentence lookups
        markdown_out_filename: Output filename for the markdown file
        lang_code: ISO 639-3 language code
        lang_name: Human-readable language name (defaults to lang_code)
        project_id: Project identifier (defaults to lang_name)
    """
    if lang_name is None:
        lang_name = lang_code
    if project_id is None:
        project_id = lang_name
    
    repeated_word_dict = defaultdict(list)
    n_repeated_words = 0
    
    # Process feedback and organize by repeated word
    for feedback_d in feedback:
        snt_id = feedback_d.get('snt-id')
        if snt := corpus.lookup_snt(snt_id):
            repeated_word = feedback_d.get('repeated-word')
            surf = feedback_d.get('surf')
            start_position = feedback_d.get('start-position')
            legitimate = feedback_d.get('legitimate')
            
            # For markdown, we'll use different formatting instead of colors
            # Use bold for illegitimate, italic for legitimate
            end_position = start_position + len(surf)
            if legitimate:
                marked_up_verse = (f"{snt[:start_position]}"
                                   f"*{snt[start_position:end_position]}*"
                                   f"{snt[end_position:]}")
            else:
                marked_up_verse = (f"{snt[:start_position]}"
                                   f"**{snt[start_position:end_position]}**"
                                   f"{snt[end_position:]}")
            
            repeated_word_dict[repeated_word].append({
                'verse': marked_up_verse,
                'snt_id': snt_id,
                'legitimate': legitimate
            })
            n_repeated_words += 1
    
    # Write to markdown file
    with open(markdown_out_filename, 'w', encoding='utf-8') as f_md:
        date = f"{datetime.datetime.now():%B %-d, %Y at %-H:%M}"
        
        # Write header
        f_md.write(f"# 🦉 Greek Room Repeated Word Check for {project_id}\n\n")
        f_md.write(f"**Date:** {date}\n\n")
        
        # Write summary
        s = "" if n_repeated_words == 1 else "s"
        f_md.write(f"### Checking for repeated words (consecutive duplicates): **{n_repeated_words}** instance{s}\n\n")
        
        # Write repeated words section
        f_md.write("## Repeated Words Found\n\n")
        
        # Sort by frequency (descending) and then alphabetically
        for duplicate in sorted(repeated_word_dict.keys(), 
                               key=lambda x: (-len(repeated_word_dict[x]), x)):
            n_instances = len(repeated_word_dict[duplicate])
            
            # Check if this is a legitimate duplicate
            legit_dupl_dict = misc_data_dict.get((lang_code, 'legitimate-duplicate', duplicate))
            
            if legit_dupl_dict:
                # Add metadata for legitimate duplicates
                f_md.write(f"### *{duplicate}* ({n_instances} instance{'s' if n_instances != 1 else ''})\n\n")
                
                try:
                    eng_gloss = legit_dupl_dict['gloss'].get('eng')
                except (KeyError, AttributeError):
                    eng_gloss = None
                
                rom = legit_dupl_dict.get('rom')
                non_latin_characters = regex.findall(r'(?V1)[\pL--\p{Latin}]', duplicate)
                
                # Add metadata block
                metadata_lines = []
                if rom and non_latin_characters:
                    metadata_lines.append(f"**Romanization:** {rom}")
                if eng_gloss:
                    metadata_lines.append(f"**English gloss:** {eng_gloss}")
                metadata_lines.append(f"**_{duplicate}_** is listed as legitimate for {lang_name}")
                
                if metadata_lines:
                    f_md.write(f"> {' | '.join(metadata_lines)}\n\n")
            else:
                # Potentially problematic duplicate
                f_md.write(f"### **{duplicate}** ({n_instances} instance{'s' if n_instances != 1 else ''})\n\n")
            
            # Write instances
            for entry in repeated_word_dict[duplicate]:
                verse = entry['verse']
                snt_id = entry['snt_id']
                f_md.write(f"- {verse} `({snt_id})`\n")
            
            f_md.write("\n")
        
        # Footer
        f_md.write("---\n\n")
        f_md.write("*Generated by Greek Room Analysis Tool*\n")
    
    # Log output location
    cwd_path = Path(os.getcwd())
    full_markdown_output_filename = (markdown_out_filename
                                     if markdown_out_filename.startswith('/')
                                     else (cwd_path / markdown_out_filename))
    sys.stderr.write(f"Wrote Markdown to {full_markdown_output_filename}\n")


def generate_markdown_string(feedback: list, misc_data_dict: dict, corpus, 
                             lang_code: str, lang_name: Optional[str] = None, 
                             project_id: Optional[str] = None) -> str:
    """
    Generate markdown content as a string instead of writing to a file.
    Useful for API responses.
    
    Args:
        feedback: List of feedback dictionaries containing repeated word information
        misc_data_dict: Dictionary containing legitimate duplicate data
        corpus: Corpus object containing sentence lookups
        lang_code: ISO 639-3 language code
        lang_name: Human-readable language name (defaults to lang_code)
        project_id: Project identifier (defaults to lang_name)
    
    Returns:
        String containing the markdown formatted content
    """
    if lang_name is None:
        lang_name = lang_code
    if project_id is None:
        project_id = lang_name
    
    repeated_word_dict = defaultdict(list)
    n_repeated_words = 0
    
    # Process feedback and organize by repeated word
    for feedback_d in feedback:
        snt_id = feedback_d.get('snt-id')
        if snt := corpus.lookup_snt(snt_id):
            repeated_word = feedback_d.get('repeated-word')
            surf = feedback_d.get('surf')
            start_position = feedback_d.get('start-position')
            legitimate = feedback_d.get('legitimate')
            
            # For markdown, we'll use different formatting instead of colors
            # Use bold for illegitimate, italic for legitimate
            end_position = start_position + len(surf)
            if legitimate:
                marked_up_verse = (f"{snt[:start_position]}"
                                   f"*{snt[start_position:end_position]}*"
                                   f"{snt[end_position:]}")
            else:
                marked_up_verse = (f"{snt[:start_position]}"
                                   f"**{snt[start_position:end_position]}**"
                                   f"{snt[end_position:]}")
            
            repeated_word_dict[repeated_word].append({
                'verse': marked_up_verse,
                'snt_id': snt_id,
                'legitimate': legitimate
            })
            n_repeated_words += 1
    
    # Build markdown string
    lines = []
    date = f"{datetime.datetime.now():%B %-d, %Y at %-H:%M}"
    
    # Header
    lines.append(f"# 🦉 Greek Room Repeated Word Check for {project_id}\n")
    lines.append(f"**Date:** {date}\n")
    
    # Summary
    s = "" if n_repeated_words == 1 else "s"
    lines.append(f"### Checking for repeated words (consecutive duplicates): **{n_repeated_words}** instance{s}\n")
    
    # Repeated words section
    lines.append("## Repeated Words Found\n")
    
    # Sort by frequency (descending) and then alphabetically
    for duplicate in sorted(repeated_word_dict.keys(), 
                           key=lambda x: (-len(repeated_word_dict[x]), x)):
        n_instances = len(repeated_word_dict[duplicate])
        
        # Check if this is a legitimate duplicate
        legit_dupl_dict = misc_data_dict.get((lang_code, 'legitimate-duplicate', duplicate))
        
        if legit_dupl_dict:
            # Add metadata for legitimate duplicates
            lines.append(f"### *{duplicate}* ({n_instances} instance{'s' if n_instances != 1 else ''})\n")
            
            try:
                eng_gloss = legit_dupl_dict['gloss'].get('eng')
            except (KeyError, AttributeError):
                eng_gloss = None
            
            rom = legit_dupl_dict.get('rom')
            non_latin_characters = regex.findall(r'(?V1)[\pL--\p{Latin}]', duplicate)
            
            # Add metadata block
            metadata_lines = []
            if rom and non_latin_characters:
                metadata_lines.append(f"**Romanization:** {rom}")
            if eng_gloss:
                metadata_lines.append(f"**English gloss:** {eng_gloss}")
            metadata_lines.append(f"**_{duplicate}_** is listed as legitimate for {lang_name}")
            
            if metadata_lines:
                lines.append(f"> {' | '.join(metadata_lines)}\n")
        else:
            # Potentially problematic duplicate
            lines.append(f"### **{duplicate}** ({n_instances} instance{'s' if n_instances != 1 else ''})\n")
        
        # Write instances
        for entry in repeated_word_dict[duplicate]:
            verse = entry['verse']
            snt_id = entry['snt_id']
            lines.append(f"- {verse} `({snt_id})`")
        
        lines.append("")
    
    # Footer
    lines.append("---\n")
    lines.append("*Generated by Greek Room Analysis Tool*")
    
    return "\n".join(lines)


def generate_whatsapp_friendly_string(feedback: list, misc_data_dict: dict, corpus, 
                                     lang_code: str, lang_name: Optional[str] = None, 
                                     project_id: Optional[str] = None) -> str:
    """
    Generate WhatsApp-friendly text content as a string instead of writing to a file.
    Uses simple text formatting compatible with WhatsApp.
    
    Args:
        feedback: List of feedback dictionaries containing repeated word information
        misc_data_dict: Dictionary containing legitimate duplicate data
        corpus: Corpus object containing sentence lookups
        lang_code: ISO 639-3 language code
        lang_name: Human-readable language name (defaults to lang_code)
        project_id: Project identifier (defaults to lang_name)
    
    Returns:
        String containing the WhatsApp-friendly formatted content
    """
    if lang_name is None:
        lang_name = lang_code
    if project_id is None:
        project_id = lang_name
    
    repeated_word_dict = defaultdict(list)
    n_repeated_words = 0
    
    # Process feedback and organize by repeated word
    for feedback_d in feedback:
        snt_id = feedback_d.get('snt-id')
        if snt := corpus.lookup_snt(snt_id):
            repeated_word = feedback_d.get('repeated-word')
            surf = feedback_d.get('surf')
            start_position = feedback_d.get('start-position')
            legitimate = feedback_d.get('legitimate')
            
            # For WhatsApp, use _italic_ for legitimate, *bold* for illegitimate
            end_position = start_position + len(surf)
            if legitimate:
                marked_up_verse = (f"{snt[:start_position]}"
                                   f"_{snt[start_position:end_position]}_"
                                   f"{snt[end_position:]}")
            else:
                marked_up_verse = (f"{snt[:start_position]}"
                                   f"*{snt[start_position:end_position]}*"
                                   f"{snt[end_position:]}")
            
            repeated_word_dict[repeated_word].append({
                'verse': marked_up_verse,
                'snt_id': snt_id,
                'legitimate': legitimate
            })
            n_repeated_words += 1
    
    # Build WhatsApp-friendly string
    lines = []
    date = f"{datetime.datetime.now():%B %-d, %Y at %-H:%M}"
    
    # Header
    lines.append(f"*Greek Room Repeated Word Check for {project_id}*\n")
    lines.append(f"Date: {date}\n")
    
    # Summary
    s = "" if n_repeated_words == 1 else "s"
    lines.append(f"*Checking for repeated words (consecutive duplicates):* {n_repeated_words} instance{s}\n")
    
    # Repeated words section
    lines.append("*Repeated Words Found*\n")
    
    # Sort by frequency (descending) and then alphabetically
    for duplicate in sorted(repeated_word_dict.keys(), 
                           key=lambda x: (-len(repeated_word_dict[x]), x)):
        n_instances = len(repeated_word_dict[duplicate])
        
        # Check if this is a legitimate duplicate
        legit_dupl_dict = misc_data_dict.get((lang_code, 'legitimate-duplicate', duplicate))
        
        if legit_dupl_dict:
            # Add metadata for legitimate duplicates
            lines.append(f"_{duplicate}_ ({n_instances} instance{'s' if n_instances != 1 else ''})")
            
            try:
                eng_gloss = legit_dupl_dict['gloss'].get('eng')
            except (KeyError, AttributeError):
                eng_gloss = None
            
            rom = legit_dupl_dict.get('rom')
            non_latin_characters = regex.findall(r'(?V1)[\pL--\p{Latin}]', duplicate)
            
            # Add metadata
            if rom and non_latin_characters:
                lines.append(f"  Romanization: {rom}")
            if eng_gloss:
                lines.append(f"  English gloss: {eng_gloss}")
            lines.append(f"  _{duplicate}_ is listed as legitimate for {lang_name}")
            lines.append("")
        else:
            # Potentially problematic duplicate
            lines.append(f"*{duplicate}* ({n_instances} instance{'s' if n_instances != 1 else ''})")
        
        # Write instances
        for entry in repeated_word_dict[duplicate]:
            verse = entry['verse']
            snt_id = entry['snt_id']
            lines.append(f"• {verse} ({snt_id})")
        
        lines.append("")
    
    return "\n".join(lines)
