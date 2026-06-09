{
  description = "Suyam teams-email-agent — NixOS LXC container for Teams → Claude → Email workflow";

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
      pkgs = nixpkgs.legacyPackages.${system};
    in {
      # Build the proxmox-lxc rootfs tarball:
      #   nix run github:nix-community/nixos-generators -- -f proxmox-lxc --flake .#teams-email-agent --system x86_64-linux
      packages.${system}.proxmox-lxc = nixos-generators.nixosGenerate {
        inherit system;
        format = "proxmox-lxc";
        modules = [ ./configuration.nix ];
      };

      # NixOS configuration for --flake .#teams-email-agent invocation
      nixosConfigurations.teams-email-agent = nixpkgs.lib.nixosSystem {
        inherit system;
        modules = [ ./configuration.nix ];
      };

      # Convenience alias: `nix build .#default` also builds the LXC image
      packages.${system}.default = self.packages.${system}.proxmox-lxc;
    };
}
