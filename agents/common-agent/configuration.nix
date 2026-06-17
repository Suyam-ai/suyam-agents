{ config, pkgs, modulesPath, lib, ... }:

let
  py = pkgs.python3;

  # ROOT CAUSE NOTE (CLEANUP-02): The previous expressions baked pydantic_graph (pre-1.x)
  # and pydantic_ai_slim (pre-1.x) into this flake. This was a major version gap:
  #   - pyproject.toml requires pydantic-ai[anthropic,groq] >= 1.104.0 (1.x series)
  #   - The old expressions installed the 0.x series (pre-rename, incompatible API surface)
  #   - 0.x had no Agent class; 1.x has a completely different module surface
  #   - Agents failed at runtime with ImportError or AttributeError
  # Fix: replace both pre-1.x expressions with pydantic-ai 1.107.0.
  # In 1.x, pydantic_ai is a meta-package wrapping pydantic_ai_slim; both are provided below.
  # The actual Python module lives in pydantic_ai_slim.
  #
  # nix-prefetch: hashes obtained via sha256sum of each wheel downloaded from PyPI

  pydantic-graph = py.pkgs.buildPythonPackage rec {
    pname = "pydantic_graph";
    version = "1.107.0";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/py3/p/pydantic_graph/pydantic_graph-1.107.0-py3-none-any.whl";
      hash = "sha256-ca3ZT+fhTHA5d6iVEXxHWq5sCwKndKA2xNANmmPHiwA=";
    };
    propagatedBuildInputs = with py.pkgs; [ pydantic typing-extensions ];
    doCheck = false;
  };

  genai-prices = py.pkgs.buildPythonPackage rec {
    pname = "genai_prices";
    version = "0.0.62";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/py3/g/genai_prices/genai_prices-0.0.62-py3-none-any.whl";
      hash = "sha256-XZqw2eXYHgNfiL9ZH7ao3eUnkieGrPHuJzc1j3u+AWc=";
    };
    doCheck = false;
  };

  griffelib = py.pkgs.buildPythonPackage rec {
    pname = "griffelib";
    version = "2.0.0";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/py3/g/griffelib/griffelib-2.0.0-py3-none-any.whl";
      hash = "sha256-AShIeMlmUIttbx2/+bb6YHvAYtgmHFxyU8soWwZCKn8=";
    };
    doCheck = false;
  };

  # Use nixpkgs typing-inspection (0.4.2) to avoid version conflict with
  # nixpkgs pydantic which also pulls in typing-inspection 0.4.2.
  typing-inspection = py.pkgs.typing-inspection;

  pydantic-ai-slim = py.pkgs.buildPythonPackage rec {
    pname = "pydantic_ai_slim";
    version = "1.107.0";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/py3/p/pydantic_ai_slim/pydantic_ai_slim-1.107.0-py3-none-any.whl";
      hash = "sha256-GvSbuuBqbFmPcsVNRzS6N3EAysSTyaBfqOCJvr6uDaY=";
    };
    propagatedBuildInputs = with py.pkgs; [
      pydantic
      httpx
      opentelemetry-api
      pydantic-graph
      genai-prices
      griffelib
      typing-inspection
    ];
    doCheck = false;
  };

  # pydantic-ai 1.107.0 is a meta-package; the actual module comes from pydantic-ai-slim above.
  # Install pydantic-ai-slim in the Python environment (the module name is still pydantic_ai).
  pydantic-ai = py.pkgs.buildPythonPackage rec {
    pname = "pydantic_ai";
    version = "1.107.0";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/py3/p/pydantic_ai/pydantic_ai-1.107.0-py3-none-any.whl";
      hash = "sha256-4DGIC0StfOODay9qqM4qC9czzbC4mjStumR+lt3Lp4g=";
    };
    propagatedBuildInputs = [ pydantic-ai-slim ];
    doCheck = false;
  };

  # nix-prefetch: run nix build once to get real hash, paste here, rebuild
  groq-sdk = py.pkgs.buildPythonPackage rec {
    pname = "groq";
    version = "0.28.0";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/py3/g/groq/groq-0.28.0-py3-none-any.whl";
      hash = "sha256-xvhmODccLLosozcjLnbI1BLnWWXtfjBY0wyapd/oQwM=";
    };
    propagatedBuildInputs = with py.pkgs; [
      httpx
      pydantic
      distro
      anyio
    ];
    doCheck = false;
  };

  # nix-prefetch: run nix build once to get real hash, paste here, rebuild
  # jiter is a Rust extension wheel — use manylinux x86_64 cp312 build
  jiter = py.pkgs.buildPythonPackage rec {
    pname = "jiter";
    version = "0.9.0";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/cp312/j/jiter/jiter-0.9.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl";
      hash = "sha256-/KGgKtYOwwuyMPZbwB9hHIYIsC0mn5mLwpzKhhmpGdw=";
    };
    doCheck = false;
  };

  # nix-prefetch: run nix build once to get real hash, paste here, rebuild
  anthropic-sdk = py.pkgs.buildPythonPackage rec {
    pname = "anthropic";
    version = "0.105.0";
    format = "wheel";
    src = pkgs.fetchurl {
      url = "https://files.pythonhosted.org/packages/py3/a/anthropic/anthropic-0.105.0-py3-none-any.whl";
      hash = "sha256-BWWXXzeorHvc+XwgAqpbEzN2wVfZJlmXchx/Ex5pck0=";
    };
    propagatedBuildInputs = with py.pkgs; [
      httpx
      pydantic
      typing-extensions
      anyio
      jiter
    ];
    doCheck = false;
  };

  pythonEnv = py.withPackages (ps: with ps; [
    pydantic
    httpx
    anyio
    typing-extensions
    distro
    pydantic-ai-slim
    pydantic-ai
    groq-sdk
    jiter
    anthropic-sdk
  ]);

in
{
  imports = [
    "${modulesPath}/virtualisation/proxmox-lxc.nix"
  ];

  proxmoxLXC = {
    privileged = false;
    manageNetwork = true;
    manageHostName = true;
  };

  networking.hostName = "common-agent";
  networking.useDHCP = false;
  networking.enableIPv6 = false;

  # IP address, gateway, and DNS are injected by Proxmox at container creation time
  # via the net0=...,ip=<cidr>,gw=<gw> create parameter — do NOT hardcode here.
  # Hardcoding causes IP collisions for concurrent containers and breaks any deployment
  # not using the same subnet. See teams-email-agent/configuration.nix for the correct pattern.

  services.resolved.enable = false;
  systemd.network.wait-online.enable = false;

  environment.systemPackages = [ pythonEnv ];

  system.activationScripts.suyamScripts = ''
    mkdir -p /opt/suyam
    cp ${./scripts/ai_summarize.py} /opt/suyam/ai_summarize.py
    chmod +x /opt/suyam/ai_summarize.py
    cp ${./scripts/http_request.py} /opt/suyam/http_request.py
    chmod +x /opt/suyam/http_request.py
  '';

  system.activationScripts.suyamSecrets = {
    text = ''
      if [ -d /run/secrets ]; then
        env_file=/etc/profile.d/suyam-secrets.sh
        echo "# Auto-generated by suyam activation -- do not edit" > "$env_file"
        for f in /run/secrets/SUYAM_CRED_*; do
          [ -f "$f" ] || continue
          varname=$(basename "$f")
          varval=$(cat "$f")
          # POSIX-safe quoting: single-quote wrap with embedded-single-quote escaping.
          # printf '%q' is bash-only and silently degrades to literal '%q' in dash
          # (the POSIX sh on NixOS). This approach is safe for all POSIX shells.
          escaped=$(printf '%s' "$varval" | sed "s/'/'\\\\'''/g")
          printf "export %s='%s'\n" "$varname" "$escaped" >> "$env_file"
        done
        chmod 600 "$env_file"
      fi
    '';
    deps = [];
  };

  system.stateVersion = "25.11";
}
