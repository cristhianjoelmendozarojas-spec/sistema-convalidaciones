# db/validators.py
"""
Validadores de entrada centralizados para seguridad y consistencia.
"""
import re
from functools import wraps
from flask import request, jsonify

class ValidationError(Exception):
    def __init__(self, field, message):
        self.field = field
        self.message = message
        super().__init__(message)

def sanitize_string(value, max_length=None):
    if not value:
        return ''
    result = str(value).strip()
    if max_length:
        result = result[:max_length]
    return result

def sanitize_int(value, default=None):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def sanitize_float(value, default=None):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

class Validator:
    RULES = {
        'dni': lambda v: len(v) == 8 and v.isdigit(),
        'email': lambda v: bool(re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v)),
        'phone_pe': lambda v: bool(re.match(r'^9\d{8}$', v)),
        'phone_pe_full': lambda v: bool(re.match(r'^51[9]\d{8}$', v)),
        'codigo': lambda v: bool(re.match(r'^[A-Z0-9\-]+$', v.upper())),
        'non_empty': lambda v: bool(v and str(v).strip()),
        'alphanumeric': lambda v: bool(re.match(r'^[A-Za-z0-9\s]+$', v)),
        'uppercase': lambda v: str(v).upper(),
    }
    
    def __init__(self, data=None):
        self.data = data or {}
        self.errors = {}
    
    def validate(self, field, rule_or_rules, required=True):
        value = self.data.get(field)
        
        if not value or (isinstance(value, str) and not value.strip()):
            if required:
                self.errors[field] = f'{field} es requerido'
            return None
        
        rules = rule_or_rules if isinstance(rule_or_rules, list) else [rule_or_rules]
        
        for rule in rules:
            if isinstance(rule, int):
                if len(str(value)) > rule:
                    self.errors[field] = f'{field} excede {rule} caracteres'
                continue
            
            if isinstance(rule, tuple) and rule[0] == 'range':
                min_val, max_val = rule[1]
                try:
                    num = float(value)
                    if not (min_val <= num <= max_val):
                        self.errors[field] = f'{field} debe estar entre {min_val} y {max_val}'
                except (ValueError, TypeError):
                    self.errors[field] = f'{field} debe ser un número'
                continue
            
            if callable(rule):
                if not rule(value):
                    self.errors[field] = f'{field} tiene formato inválido'
                continue
            
            if isinstance(rule, str) and rule in self.RULES:
                if not self.RULES[rule](value):
                    self.errors[field] = f'{field} tiene formato inválido'
        
        return value
    
    @property
    def is_valid(self):
        return len(self.errors) == 0
    
    def get_errors(self):
        return self.errors

def validate_json(*required_fields):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            data = request.get_json()
            if not data:
                return jsonify({'ok': False, 'error': 'JSON requerido'}), 400
            
            missing = [f for f in required_fields if f not in data or not data[f]]
            if missing:
                return jsonify({'ok': False, 'error': f'Campos requeridos: {", ".join(missing)}'}), 400
            
            return f(*args, **kwargs)
        return wrapper
    return decorator

def validate_pagination(default_per_page=20, max_per_page=100):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            page = max(1, sanitize_int(request.args.get('page', 1), 1))
            per_page = min(max_per_page, max(1, sanitize_int(request.args.get('per_page', default_per_page), default_per_page)))
            kwargs['page'] = page
            kwargs['per_page'] = per_page
            kwargs['offset'] = (page - 1) * per_page
            return f(*args, **kwargs)
        return wrapper
    return decorator
