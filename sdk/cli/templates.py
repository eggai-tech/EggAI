"""
Template generation for EggAI applications using Jinja2.

This module uses Jinja2 templates to generate boilerplate code for new EggAI applications.
"""

from pathlib import Path
from typing import TYPE_CHECKING
from jinja2 import Environment, FileSystemLoader

if TYPE_CHECKING:
    from .wizard import AppConfig


class TemplateGenerator:
    """Jinja2-based template generator for EggAI applications."""
    
    def __init__(self):
        template_dir = Path(__file__).parent / "templates"
        
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=False,
            lstrip_blocks=False
        )
    
    def generate_main_py(self, config: "AppConfig") -> str:
        """Generate the main.py file content."""
        template = self.env.get_template("main.py.j2")
        return template.render(
            project_name=config.project_name,
            transport=config.transport,
            agents=config.agents
        )
    
    def generate_agent_file(self, agent_name: str, include_console: bool = False) -> str:
        """Generate individual agent file content."""
        template = self.env.get_template("agent.py.j2")
        
        from .wizard import agent_name_to_filename
        
        filename = agent_name_to_filename(agent_name)
        agent_channel = filename.replace("_", ".")
        
        return template.render(
            agent_name=agent_name,
            agent_function=filename,
            agent_channel=agent_channel,
            include_console=include_console
        )
    
    def generate_agents_init(self) -> str:
        template = self.env.get_template("agents_init.py.j2")
        return template.render()
    
    def generate_requirements_txt(self, config: "AppConfig") -> str:
        template = self.env.get_template("requirements.txt.j2")
        return template.render(
            transport=config.transport,
            include_console=config.include_console
        )
    
    def generate_readme(self, config: "AppConfig") -> str:
        template = self.env.get_template("README.md.j2")
        return template.render(
            project_name=config.project_name,
            transport=config.transport,
            agents=config.agents
        )
    
    def generate_env_file(self) -> str:
        template = self.env.get_template("env.j2")
        return template.render()
    
    def generate_console_file(self, config: "AppConfig") -> str:
        template = self.env.get_template("console.py.j2")
        return template.render(
            project_name=config.project_name,
            transport=config.transport
        )
    
    def generate_common_models_file(self, config: "AppConfig") -> str:
        template = self.env.get_template("common_models.py.j2")
        return template.render(
            project_name=config.project_name
        )


_generator = TemplateGenerator()

def generate_main_py(config: "AppConfig") -> str:
    return _generator.generate_main_py(config)

def generate_agent_file(agent_name: str, include_console: bool = False) -> str:
    return _generator.generate_agent_file(agent_name, include_console)

def generate_agents_init() -> str:
    return _generator.generate_agents_init()

def generate_requirements_txt(config: "AppConfig") -> str:
    return _generator.generate_requirements_txt(config)

def generate_readme(config: "AppConfig") -> str:
    return _generator.generate_readme(config)

def generate_env_file() -> str:
    return _generator.generate_env_file()

def generate_console_file(config: "AppConfig") -> str:
    return _generator.generate_console_file(config)

def generate_common_models_file(config: "AppConfig") -> str:
    return _generator.generate_common_models_file(config)