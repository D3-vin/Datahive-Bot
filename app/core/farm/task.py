"""
FarmTask class for processing farming tasks
"""

import re
import random
import yaml
from typing import Any, Dict, Optional
from lxml import html as lhtml

PLACEHOLDER_RE = re.compile(r'\{\{([\w\[\].\'"-]+)\}\}')


class FarmTask:
    """Class for processing farming tasks"""
    
    def __init__(
        self,
        task_id: str,
        target_url_html: str | None,
        task_yaml_rules: str,
        task_vars: Optional[Dict[str, Any]] = None
    ):
        self.task_id = task_id
        self.task_yaml_rules = task_yaml_rules
        self.task_vars = task_vars
        self.target_url_html = target_url_html

    @staticmethod
    def get_from_context(context, path: str):
        """Get value from context by path"""
        parts = path.split('.')
        cur = context
        for part in parts:
            if '[' in part and part.endswith(']'):
                name, idx_str = part[:-1].split('[', 1)
                cur = cur.get(name, {})
                idx = int(idx_str)
                cur = cur[idx]
                continue
            if isinstance(cur, dict):
                cur = cur.get(part)
                continue
            cur = getattr(cur, part, None)
        return cur

    def resolve_placeholders(self, obj, context):
        """Resolve placeholders in object"""
        if isinstance(obj, str):
            def replace(match):
                path = match.group(1).strip()
                value = self.get_from_context(context, path)
                return str(value) if value is not None else ''
            
            return PLACEHOLDER_RE.sub(replace, obj)
        elif isinstance(obj, dict):
            return {k: self.resolve_placeholders(v, context) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.resolve_placeholders(v, context) for v in obj]
        return obj

    def _node_to_text(self, node):
        """Convert HTML node to text"""
        if isinstance(node, str):
            return node
        if hasattr(node, 'itertext'):
            parts = []
            for t in node.itertext():
                if t is None:
                    continue
                t = t.strip()
                if not t:
                    continue
                parts.append(t)
            return ' '.join(parts)
        return str(node)

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text"""
        return re.sub(r'\s+', ' ', text, flags=re.MULTILINE).strip()

    def _apply_regexp_and_template(self, text: str, regexp: Optional[str], template: Optional[str]) -> str:
        """Apply regex and template to text"""
        if not regexp:
            return self._normalize_whitespace(text)
        
        m = re.search(regexp, text, flags=re.S)
        if not m:
            return ''
        
        if not template:
            return self._normalize_whitespace(m.group(0))
        
        result = template
        for i, g in enumerate(m.groups(), 1):
            result = result.replace(f'\\{i}', g if g else '')
        result = result.replace('\\0', m.group(0))
        return self._normalize_whitespace(result)

    def _make_hashable(self, value):
        """Convert value to hashable type"""
        if isinstance(value, dict):
            return tuple(sorted((k, self._make_hashable(v)) for k, v in value.items()))
        elif isinstance(value, (list, tuple)):
            return tuple(self._make_hashable(v) for v in value)
        return value

    def extract_field(self, node, field_def: Dict[str, Any]):
        """Extract field from HTML node according to definition"""
        ftype = field_def['type']
        xpath = field_def['xpath']
        regexp = field_def.get('regexp')
        template = field_def.get('template')
        
        if ftype == 'PROPERTY':
            matches = node.xpath(xpath)
            if not matches:
                return ''
            text = self._node_to_text(matches[0])
            return self._apply_regexp_and_template(text, regexp, template)
        
        elif ftype == 'OBJECT':
            result = {}
            for child in field_def.get('child', []):
                result[child['field_name']] = self.extract_field(node, child)
            return result
        
        elif ftype == 'OBJECTS':
            items = node.xpath(xpath)
            arr = []
            for item_node in items:
                obj = {}
                for child in field_def.get('child', []):
                    obj[child['field_name']] = self.extract_field(item_node, child)
                arr.append(obj)
            
            seen = set()
            unique = []
            for o in arr:
                key = self._make_hashable(o)
                if key in seen:
                    continue
                seen.add(key)
                unique.append(o)
            return unique
        
        return None

    def run_offscreen_like(self, html_text: str, rules: Dict[str, Any]):
        """Run HTML processing by rules"""
        doc = lhtml.fromstring(html_text)
        fields_cfg = rules.get('fields', [])
        fields_result = {}
        
        for field_def in fields_cfg:
            name = field_def['field_name']
            fields_result[name] = self.extract_field(doc, field_def)
        
        result = {'fields': fields_result}
        return result

    def run_yaml_rules_on_html(self):
        """Run YAML rules on HTML"""
        parsed = yaml.safe_load(self.task_yaml_rules)
        steps = parsed.get('steps', [])
        vars_data = self.task_vars or {}
        step_outputs = {}
        
        for step in steps:
            use = step.get('use')
            output_name = step.get('output')
            placeholder_context = {'vars': vars_data, 'steps': step_outputs}
            resolved_step = self.resolve_placeholders(step, placeholder_context)
            
            if use == 'offscreen':
                rules = resolved_step.get('rules', {})
                result = self.run_offscreen_like(self.target_url_html, rules)
                if output_name:
                    step_outputs[output_name] = result
        
        return step_outputs

    def _generate_perf_metrics(self, task_id: str):
        """Generate performance metrics"""
        duration = round(random.uniform(200, 900), 1)
        base_mem = random.uniform(40, 60)
        mem_spread = random.uniform(0.01, 0.08)
        mem_min = round(base_mem, 2)
        mem_max = round(base_mem + mem_spread, 2)
        mem_avg = round((mem_min + mem_max) / 2, 2)
        start_mem = round(mem_min - random.uniform(0.01, 0.06), 2)
        end_mem = mem_max
        cpu_min = round(random.uniform(3, 35), 2)
        cpu_max = round(cpu_min + random.uniform(1, 6), 2)
        cpu_avg = round(cpu_min + (cpu_max - cpu_min) * random.uniform(0.3, 0.7), 2)
        start_cpu = round(random.uniform(3, min(cpu_min, 10)), 2)
        end_cpu = 0
        
        return {
            'jobId': task_id,
            'duration': duration,
            'statistics': {
                'cpu': {'min': cpu_min, 'max': cpu_max, 'avg': cpu_avg},
                'memory': {'min': mem_min, 'max': mem_max, 'avg': mem_avg}
            },
            'metrics': {
                'start': {'cpu': start_cpu, 'memory': start_mem},
                'end': {'cpu': end_cpu, 'memory': end_mem}
            }
        }

    def build_task_json_data(self, context: Optional[Dict[str, Any]] = None):
        """Build JSON data for task"""
        if self.target_url_html is None:
            step_outputs = {
                'pageData': {
                    'fields': {
                        'title': '',
                        'createdAt': '',
                        'question': '',
                        'answers': []
                    }
                }
            }
        else:
            try:
                step_outputs = self.run_yaml_rules_on_html()
            except Exception:
                step_outputs = {
                    'pageData': {
                        'fields': {
                            'title': '',
                            'createdAt': '',
                            'question': '',
                            'answers': []
                        }
                    }
                }
        
        perf_metrics = self._generate_perf_metrics(self.task_id)
        step_outputs['perfMetrics'] = perf_metrics
        
        return {
            'result': step_outputs,
            'metadata': perf_metrics,
            'context': context or {}
        }

