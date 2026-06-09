{
  description = "Suyam email-agent — NixOS LXC container for email.smtp and email.m365 steps";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    nixos-generators = {
      url = "github:nix-community/nixos-generators";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, nixos-generators, ... }:
    let
      system = "x86_64-linux";
    in {
      packages.${system} = let
        lxc = nixos-generators.nixosGenerate {
          inherit system;
          format = "proxmox-lxc";
          modules = [ ./configuration.nix ];
        };
      in {
        proxmox-lxc = lxc;
        default = lxc;
      };

      nixosConfigurations.email-agent = nixpkgs.lib.nixosSystem {
        inherit system;
        modules = [ ./configuration.nix ];
      };
    };
}
