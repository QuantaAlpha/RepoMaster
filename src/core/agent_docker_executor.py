from __future__ import annotations

import uuid
from pathlib import Path
from typing import Dict, List, Optional, Union

import docker
from autogen.coding import DockerCommandLineCodeExecutor, LocalCommandLineCodeExecutor
from autogen.coding.base import CodeBlock, CommandLineCodeResult

class EnhancedDockerCommandLineCodeExecutor(DockerCommandLineCodeExecutor):
    """
    Enhanced version of DockerCommandLineCodeExecutor that supports keeping
    the same path structure between host and container.
    
    Usage:
        # Standard usage (same as parent class)
        executor = EnhancedDockerCommandLineCodeExecutor()
        
        # With same path structure
        executor = EnhancedDockerCommandLineCodeExecutor(
            image="your_docker_image",
            work_dir="/home/user/project",
            keep_same_path=True,
            timeout=300,
        )
        # Now container will have the same path: /home/user/project
    
    Note:
        - When keep_same_path=True, ensure Docker has permissions to access the path
        - The path must be absolute and exist on the host system
        - This is useful for maintaining consistent file paths across host and container
    """
    
    def __init__(
        self,
        image: str = "python:3-slim",
        container_name: Optional[str] = None,
        timeout: int = 60,
        work_dir: Union[Path, str] = Path("."),
        bind_dir: Optional[Union[Path, str]] = None,
        auto_remove: bool = True,
        stop_container: bool = True,
        execution_policies: Optional[Dict[str, bool]] = None,
        keep_same_path: bool = False,
        network_mode: str = "host",  # Add network mode configuration
    ):
        """
        Initialize the enhanced Docker code executor.
        
        Args:
            keep_same_path (bool): If True, keeps the same path structure 
                                 between host and container. Defaults to False.
            network_mode (str): Network mode for the container. Options:
                              - "host": Use host network (recommended for network access)
                              - "bridge": Use bridge network with DNS configuration
                              - "none": No networking. Defaults to "host".
            Other args: Same as parent class.
        """
        self._keep_same_path = keep_same_path
        self._network_mode = network_mode
        
        if not keep_same_path:
            # Use parent class default behavior
            super().__init__(
                image, container_name, timeout, work_dir, bind_dir,
                auto_remove, stop_container, execution_policies
            )
        else:
            # When custom mount logic is needed, manually create container
            self._custom_init(
                image, container_name, timeout, work_dir, bind_dir,
                auto_remove, stop_container, execution_policies, network_mode
            )
    
    def _custom_init(
        self,
        image: str,
        container_name: Optional[str],
        timeout: int,
        work_dir: Union[Path, str],
        bind_dir: Optional[Union[Path, str]],
        auto_remove: bool,
        stop_container: bool,
        execution_policies: Optional[Dict[str, bool]],
        network_mode: str,
    ):
        """Custom initialization with same path mounting."""
        # Parameter validation and processing (reuse parent class logic)
        if timeout < 1:
            raise ValueError("Timeout must be greater than or equal to 1.")

        if isinstance(work_dir, str):
            work_dir = Path(work_dir)
        work_dir.mkdir(exist_ok=True)

        if bind_dir is None:
            bind_dir = work_dir
        elif isinstance(bind_dir, str):
            bind_dir = Path(bind_dir)

        # Docker client and image processing
        client = docker.from_env()
        try:
            client.images.get(image)
        except docker.errors.ImageNotFound:
            import logging
            logging.info(f"Pulling image {image}...")
            client.images.pull(image)

        if container_name is None:
            container_name = f"autogen-code-exec-{uuid.uuid4()}"

        # Key difference: use same path mounting
        bind_source = str(bind_dir.resolve())
        bind_target = str(bind_dir.resolve())  # Target path same as source path
        container_work_dir = str(work_dir.resolve())
        
        # Configure container parameters based on network mode
        container_kwargs = {
            "image": image,
            "name": container_name,
            "entrypoint": "/bin/sh",
            "tty": True,
            "auto_remove": auto_remove,
            "volumes": {bind_source: {"bind": bind_target, "mode": "rw"}},
            "working_dir": container_work_dir,
            "network_mode": network_mode,
        }
        
        # Only set DNS in non-host network mode
        if network_mode != "host":
            container_kwargs["dns"] = ["8.8.8.8", "8.8.4.4"]
        
        # Create container
        self._container = client.containers.create(**container_kwargs)
        
        self._container.start()
        
        # Wait for container ready
        from autogen.coding.docker_commandline_code_executor import _wait_for_ready
        _wait_for_ready(self._container)

        # Set cleanup function
        import atexit
        def cleanup() -> None:
            try:
                container = client.containers.get(container_name)
                container.stop()
            except docker.errors.NotFound:
                pass
            atexit.unregister(cleanup)

        if stop_container:
            atexit.register(cleanup)

        self._cleanup = cleanup

        # Check container status
        if self._container.status != "running":
            raise ValueError(f"Failed to start container from image {image}. Logs: {self._container.logs()}")

        # Set instance variables
        self._timeout = timeout
        self._work_dir: Path = work_dir
        self._bind_dir: Path = bind_dir
        self.execution_policies = self.DEFAULT_EXECUTION_POLICY.copy()
        if execution_policies is not None:
            self.execution_policies.update(execution_policies)

    def execute_code_blocks(self, code_blocks: List[CodeBlock]) -> CommandLineCodeResult:
        """
        Execute code blocks with enhanced path handling.
        """
        if not self._keep_same_path:
            # Use parent class default logic
            return super().execute_code_blocks(code_blocks)
        
        # Use modified execution logic
        return self._execute_with_full_paths(code_blocks)
    
    def _execute_with_full_paths(self, code_blocks: List[CodeBlock]) -> CommandLineCodeResult:
        """Execute code blocks using full paths instead of relative paths."""
        if len(code_blocks) == 0:
            raise ValueError("No code blocks to execute.")

        outputs = []
        files = []
        last_exit_code = 0
        
        for code_block in code_blocks:
            # Language validation (reuse parent class logic)
            lang = self.LANGUAGE_ALIASES.get(code_block.language.lower(), code_block.language.lower())
            if lang not in self.DEFAULT_EXECUTION_POLICY:
                outputs.append(f"Unsupported language {lang}\n")
                last_exit_code = 1
                break

            execute_code = self.execution_policies.get(lang, False)
            
            # Code processing (reuse parent class logic)
            from autogen.coding.utils import silence_pip, _get_file_name_from_content
            from hashlib import md5
            
            code = silence_pip(code_block.code, lang)

            # Filename processing (reuse parent class logic)
            try:
                filename = _get_file_name_from_content(code, self._work_dir)
            except ValueError:
                outputs.append("Filename is not in the workspace")
                last_exit_code = 1
                break

            if not filename:
                filename = f"tmp_code_{md5(code.encode()).hexdigest()}.{lang}"

            # Save file (reuse parent class logic)
            code_path = self._work_dir / filename
            with code_path.open("w", encoding="utf-8") as fout:
                fout.write(code)
            files.append(code_path)

            if not execute_code:
                outputs.append(f"Code saved to {str(code_path)}\n")
                continue

            # Key modification: use absolute paths instead of relative paths
            container_file_path = str(code_path.resolve())
            
            # Execute command (reuse parent class logic)
            from autogen.code_utils import _cmd, TIMEOUT_MSG
            command = ["timeout", str(self._timeout), _cmd(lang), container_file_path]
            result = self._container.exec_run(command)
            exit_code = result.exit_code
            output = result.output.decode("utf-8")
            
            if exit_code == 124:
                output += "\n" + TIMEOUT_MSG
            outputs.append(output)

            last_exit_code = exit_code
            if exit_code != 0:
                break

        # Return result (reuse parent class logic)
        code_file = str(files[0]) if files else None
        return CommandLineCodeResult(exit_code=last_exit_code, output="".join(outputs), code_file=code_file)

    @property
    def keep_same_path(self) -> bool:
        """Whether to keep the same path structure between host and container."""
        return self._keep_same_path
    
    @property 
    def network_mode(self) -> str:
        """The network mode used by the container."""
        return getattr(self, '_network_mode', 'bridge')