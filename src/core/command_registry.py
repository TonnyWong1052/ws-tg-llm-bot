import logging
import re
import inspect
from functools import wraps

logger = logging.getLogger("command_registry")

class CommandRegistry:
    """
    Command registry for managing and dispatching commands
    """
    def __init__(self):
        self.commands = {}
        self.platform_handlers = {}
    
    def register(self, command_name, pattern=None, platform=None, description=None, help_text=None):
        """
        Decorator for registering commands
        
        Args:
            command_name (str): Command name
            pattern (str, optional): Regex pattern for the command
            platform (str, optional): Platform name, if specified the command will only be available for that platform
            description (str, optional): Command description
            help_text (str, optional): Help text
            
        Returns:
            function: Decorator function
        """
        def decorator(func):
            cmd_pattern = pattern or f"^/{command_name}(?:\\s+(.+))?$"
            
            # Extract description from function docstring if not provided
            cmd_description = description
            cmd_help = help_text
            
            if not cmd_description and func.__doc__:
                doc_lines = inspect.getdoc(func).split('\n')
                cmd_description = doc_lines[0].strip() if doc_lines else None
                if len(doc_lines) > 1:
                    # Use rest of docstring as help text
                    cmd_help = '\n'.join(doc_lines[1:]).strip()
            
            # Register command
            cmd_info = {
                'name': command_name,
                'pattern': re.compile(cmd_pattern),
                'handler': func,
                'description': cmd_description or f"Handle {command_name} command",
                'help': cmd_help or f"Usage: /{command_name} [arguments]",
                'platform': platform
            }
            
            if platform:
                if platform not in self.platform_handlers:
                    self.platform_handlers[platform] = {}
                self.platform_handlers[platform][command_name] = cmd_info
            else:
                self.commands[command_name] = cmd_info
                
            logger.info(f"Registered command: {command_name} for {'all platforms' if not platform else platform}")
            
            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            
            return wrapper
            
        return decorator
    
    def get_command(self, command_name, platform=None):
        """
        Get the handler for the specified command
        
        Args:
            command_name (str): Command name
            platform (str, optional): Platform name
            
        Returns:
            dict or None: Command info, or None if not found
        """
        # Check platform-specific commands first
        if platform and platform in self.platform_handlers:
            if command_name in self.platform_handlers[platform]:
                return self.platform_handlers[platform][command_name]
        
        # Then check generic commands
        return self.commands.get(command_name)
    
    def match_command(self, text, platform=None):
        """
        Match message text to registered commands
        
        Args:
            text (str): Message text
            platform (str, optional): Platform name
            
        Returns:
            tuple: (command_info, match_object) or (None, None)
        """
        # Check platform-specific commands
        if platform:
            platform_commands = self.platform_handlers.get(platform, {})
            for cmd_info in platform_commands.values():
                match = cmd_info['pattern'].match(text)
                if match:
                    return cmd_info, match
        
        # Check generic commands
        for cmd_info in self.commands.values():
            match = cmd_info['pattern'].match(text)
            if match:
                return cmd_info, match
                
        return None, None
    
    def get_help_text(self, command_name=None, platform=None):
        """
        Get help text for a command
        
        Args:
            command_name (str, optional): Command name, if not specified returns help for all commands
            platform (str, optional): Platform name
            
        Returns:
            str: Help text
        """
        if command_name:
            cmd_info = self.get_command(command_name, platform)
            if cmd_info:
                return f"/{cmd_info['name']} - {cmd_info['description']}\n\n{cmd_info['help']}"
            return f"Command /{command_name} not found."
        
        # List all available commands
        help_text = "Available commands:\n\n"
        
        # Add generic commands
        for cmd_name, cmd_info in sorted(self.commands.items()):
            help_text += f"/{cmd_name} - {cmd_info['description']}\n"
        
        # Add platform-specific commands
        if platform and platform in self.platform_handlers:
            platform_cmds = self.platform_handlers[platform]
            if platform_cmds:
                help_text += f"\n{platform.capitalize()} specific commands:\n\n"
                for cmd_name, cmd_info in sorted(platform_cmds.items()):
                    help_text += f"/{cmd_name} - {cmd_info['description']}\n"
        
        return help_text

# Global command registry instance
command_registry = CommandRegistry() 