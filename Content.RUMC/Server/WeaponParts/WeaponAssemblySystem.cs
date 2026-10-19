// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2026 wray-git
using Content.Server.CMU14.Gunsmith;
using Content.Shared._RMC14.Weapons.Ranged;
using Content.Shared.CMU14.Gunsmith;
using Content.Shared.CMU14.WeaponParts;
using Content.Shared.Containers.ItemSlots;
using Content.Shared.Examine;
using Content.Shared.Hands.EntitySystems;
using Content.Shared.Popups;
using Content.Shared.Verbs;
using Robust.Shared.Audio;
using Robust.Shared.Audio.Systems;
using Robust.Shared.Prototypes;

namespace Content.Server.CMU14.WeaponParts;

// The assembly bench of weapons: four slots, a barrel, a receiver, a bolt and a grip. With all four in and made for one platform and one caliber, the verb of the bench puts
// them together into a weapon of the gunsmith (the same kind of weapon the gunsmith's bench makes, with the same behaviour in the field), whose numbers come from the parts.
public sealed class WeaponAssemblySystem : EntitySystem
{
    [Dependency] private readonly IPrototypeManager _prototypes = default!;
    [Dependency] private readonly ItemSlotsSystem _itemSlots = default!;
    [Dependency] private readonly SharedPopupSystem _popup = default!;
    [Dependency] private readonly SharedHandsSystem _hands = default!;
    [Dependency] private readonly MetaDataSystem _meta = default!;
    [Dependency] private readonly SharedAudioSystem _audio = default!;
    [Dependency] private readonly RMCSelectiveFireSystem _selective = default!;

    private static readonly SoundSpecifier AssembledSound = new SoundPathSpecifier("/Audio/Machines/ding.ogg");

    public override void Initialize()
    {
        base.Initialize();

        SubscribeLocalEvent<WeaponAssemblyBenchComponent, GetVerbsEvent<AlternativeVerb>>(OnGetVerbs);
        SubscribeLocalEvent<WeaponAssemblyBenchComponent, ExaminedEvent>(OnExamined);
    }

    // ------------------------------------------------------------------ what is in the bench

    public Dictionary<WeaponPartKind, WeaponPartComponent> PartsOf(EntityUid bench)
    {
        var parts = new Dictionary<WeaponPartKind, WeaponPartComponent>();
        foreach (var (kind, slot) in WeaponAssemblyBenchComponent.Slots)
        {
            if (_itemSlots.GetItemOrNull(bench, slot) is { } item && TryComp<WeaponPartComponent>(item, out var part) && part.Kind == kind)
                parts[kind] = part;
        }

        return parts;
    }

    // The weapon the parts in the bench come to, or the errors that stop it.
    public WeaponAssemblyResult Preview(EntityUid bench, out WeaponPlatformPrototype? platform, out GunsmithActionPrototype? action)
    {
        platform = null;
        action = null;
        var parts = PartsOf(bench);

        if (!parts.TryGetValue(WeaponPartKind.Receiver, out var receiver) ||
            !_prototypes.TryIndex<WeaponPlatformPrototype>(receiver.Platform, out platform))
        {
            var missing = new WeaponAssemblyResult();
            foreach (var kind in Enum.GetValues<WeaponPartKind>())
            {
                if (!parts.ContainsKey(kind))
                    missing.Errors.Add("weaponparts-error-missing-" + kind.ToString().ToLowerInvariant());
            }

            if (missing.Errors.Count == 0)
                missing.Errors.Add("weaponparts-error-platform");

            return missing;
        }

        if (!_prototypes.TryIndex<GunsmithActionPrototype>(platform.Action, out action) ||
            !_prototypes.TryIndex<GunsmithCaliberPrototype>(platform.Caliber, out var caliber) ||
            !_prototypes.TryIndex<GunsmithPowderPrototype>(caliber.Powder, out var powder))
        {
            var broken = new WeaponAssemblyResult();
            broken.Errors.Add("weaponparts-error-platform");
            return broken;
        }

        var spec = GunsmithCatalogSystem.SpecOf(caliber);
        return WeaponAssembler.Evaluate(platform, action, AmmoMechanics.PressureOf(spec, powder), parts);
    }

    // ------------------------------------------------------------------ the verb

    private void OnGetVerbs(Entity<WeaponAssemblyBenchComponent> bench, ref GetVerbsEvent<AlternativeVerb> args)
    {
        if (!args.CanAccess || !args.CanInteract)
            return;

        var user = args.User;
        var target = bench;
        var result = Preview(bench, out _, out _);

        args.Verbs.Add(new AlternativeVerb
        {
            Text = Loc.GetString("weaponparts-verb-assemble"),
            Priority = 3,
            Disabled = !result.Ok,
            Message = result.Ok ? null : Loc.GetString(result.Errors[0]),
            Act = () => Assemble(target, user),
        });
    }

    public bool Assemble(Entity<WeaponAssemblyBenchComponent> bench, EntityUid user)
    {
        var result = Preview(bench, out var platform, out var action);
        if (!result.Ok || platform == null || action == null)
        {
            _popup.PopupEntity(Loc.GetString(result.Errors.Count > 0 ? result.Errors[0] : "weaponparts-error-platform"), bench, user, PopupType.SmallCaution);
            return false;
        }

        var caliber = _prototypes.Index<GunsmithCaliberPrototype>(platform.Caliber);
        var spec = GunsmithCatalogSystem.SpecOf(caliber);
        var design = new FirearmDesign
        {
            Action = action.ID,
            Caliber = spec,
            BarrelLengthMm = result.BarrelLengthMm,
            Stock = platform.Stock,
            Feed = platform.Feed,
            FeedCapacity = platform.FeedCapacity,
        };

        var feedTail = platform.Feed switch
        {
            FeedKind.Revolver => "Revolver",
            FeedKind.Internal => "Internal",
            _ => string.Empty,
        };

        var proto = "RUMCCraftedFirearm" + action.ID.Replace("GunsmithAction", string.Empty) + feedTail;
        if (!_prototypes.HasIndex<EntityPrototype>(proto))
            proto = "RUMCCraftedFirearm";

        var gun = Spawn(proto, Transform(bench).Coordinates);
        PutOnTheFeed(gun, platform);
        Apply(gun, design, result, action);

        // The parts are used up.
        foreach (var (_, slot) in WeaponAssemblyBenchComponent.Slots)
        {
            if (_itemSlots.TryGetSlot(bench.Owner, slot, out var itemSlot) && itemSlot.Item is { } part)
            {
                _itemSlots.TryEject(bench.Owner, itemSlot, user, out _, excludeUserAudio: true);
                QueueDel(part);
            }
        }

        _meta.SetEntityName(gun, Loc.GetString("weaponparts-weapon-name",
            ("platform", Loc.GetString(platform.Name)), ("grade", Loc.GetString("weaponparts-grade-" + result.Grade.ToString().ToLowerInvariant()))));
        _meta.SetEntityDescription(gun, Loc.GetString("weaponparts-weapon-description"));

        _hands.TryPickupAnyHand(user, gun);
        _audio.PlayPvs(AssembledSound, bench);
        _popup.PopupEntity(Loc.GetString("weaponparts-assembled"), bench, user);
        return true;
    }

    // A weapon that is not fed from a magazine gets the feed of the capacity of its platform: the cylinder, or the magazine inside.
    private void PutOnTheFeed(EntityUid gun, WeaponPlatformPrototype platform)
    {
        if (platform.Feed == FeedKind.Magazine)
            return;

        var template = $"RUMCCraftedFeed{platform.Feed}{Math.Clamp(platform.FeedCapacity, 2, 12)}";
        if (!_prototypes.TryIndex<EntityPrototype>(template, out var proto))
            return;

        var registry = new Robust.Shared.Prototypes.ComponentRegistry();
        foreach (var (name, entry) in proto.Components)
        {
            if (name is "BallisticAmmoProvider" or "RevolverAmmoProvider")
                registry.Add(name, entry);
        }

        EntityManager.AddComponents(gun, registry);
    }

    // Gives the weapon the numbers of the parts; what the gun of the game asks for in the field (the rate, the scatter, the jams, the bursts) is read from them by CraftedFirearmSystem.
    private void Apply(EntityUid gun, FirearmDesign design, WeaponAssemblyResult e, GunsmithActionPrototype action)
    {
        var crafted = EnsureComp<CraftedFirearmComponent>(gun);

        crafted.Design = design.Clone();
        crafted.CaliberKey = design.Caliber.Key();
        crafted.Damage = e.Damage;
        crafted.MuzzleVelocity = e.MuzzleVelocity;
        crafted.PressureMpa = e.PressureMpa;
        crafted.BarrelMisesMpa = e.BarrelMisesMpa;
        crafted.BarrelYieldMpa = e.BarrelYieldMpa;
        crafted.BarrelLimitTempC = e.BarrelLimitTempC;
        crafted.WeakestSafety = e.WeakestSafety;
        crafted.StockSafety = e.StockSafety;
        crafted.HingeSafety = e.HingeSafety;
        crafted.FatigueLifeShots = e.FatigueLifeShots;
        crafted.HeatPerShotK = e.HeatPerShotK;
        crafted.Reliability = e.Reliability;
        crafted.Quality = e.Quality;
        crafted.Rear = GunsmithSprites.Rear(design, action);
        crafted.Mid = GunsmithSprites.Mid(action);
        crafted.Front = GunsmithSprites.Front(design);
        Dirty(gun, crafted);

        crafted.FireRate = e.FireRate;
        crafted.Modes = e.Modes;
        crafted.ScatterDegrees = e.ScatterDegrees;
        crafted.RecoilFactor = e.RecoilFactor;
        Dirty(gun, crafted);
        _selective.RefreshFireModes((gun, null), true);
    }

    // ------------------------------------------------------------------ the examine text

    private void OnExamined(Entity<WeaponAssemblyBenchComponent> bench, ref ExaminedEvent args)
    {
        if (!args.IsInDetailsRange)
            return;

        using var group = args.PushGroup(nameof(WeaponAssemblyBenchComponent));
        foreach (var (kind, slot) in WeaponAssemblyBenchComponent.Slots)
        {
            var item = _itemSlots.GetItemOrNull(bench.Owner, slot);
            args.PushMarkup(Loc.GetString("weaponparts-examine-slot",
                ("kind", Loc.GetString("weaponparts-kind-" + kind.ToString().ToLowerInvariant())),
                ("part", item == null ? Loc.GetString("weaponparts-examine-empty") : Name(item.Value))));
        }

        var result = Preview(bench, out _, out _);
        if (!result.Ok)
        {
            args.PushMarkup(Loc.GetString(result.Errors[0]));
            return;
        }

        args.PushMarkup(Loc.GetString("weaponparts-examine-stats",
            ("rate", result.FireRate.ToString("0.0")),
            ("scatter", result.ScatterDegrees.ToString("0.0")),
            ("recoil", result.RecoilFactor.ToString("0.0")),
            ("reliability", (int) Math.Round(result.Reliability * 100)),
            ("safety", result.WeakestSafety.ToString("0.0"))));
    }
}
