// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2026 wray-git
using Content.Shared.CMU14.Gunsmith;
using Robust.Shared.GameStates;
using Robust.Shared.Prototypes;

namespace Content.Shared.CMU14.WeaponParts;

// The four parts a weapon is put together of at the assembly bench.
public enum WeaponPartKind : byte
{
    Barrel,
    Receiver,
    Bolt,
    Grip,
}

// How well a part is made: crude, standard or fine. The better it is made, the stronger, the more reliable and the truer it is, and the dearer it is.
public enum WeaponPartGrade : byte
{
    Crude,
    Standard,
    Fine,
}

// A part of a weapon: a barrel, a receiver, a bolt or a grip. It is made at a machine of the electric stage and put into a slot of the assembly bench.
// The numbers of the part are what it adds to the weapon (see WeaponAssembler for how they are put together).
[RegisterComponent, NetworkedComponent]
public sealed partial class WeaponPartComponent : Component
{
    [DataField(required: true)]
    public WeaponPartKind Kind;

    [DataField]
    public WeaponPartGrade Grade = WeaponPartGrade.Standard;

    // The platform (a pistol, a carbine, a shotgun) the part is for: a part of another platform does not fit.
    [DataField(required: true)]
    public string Platform = string.Empty;

    // The caliber of a barrel or of a bolt (the id of a gunsmith caliber): the two must be the same.
    [DataField]
    public string Caliber = string.Empty;

    // The length of a barrel, mm.
    [DataField]
    public double BarrelLengthMm;

    // How much a part is worth against the strain of the shot: the stress it can take, as a factor of the pressure of the normal load.
    [DataField]
    public double Safety = 1.5;

    // The share of the shots that do not jam because of this part.
    [DataField]
    public double Reliability = 0.95;

    // A barrel: the damage and the shots it lasts, and how it heats. A bolt: the rate of fire. A grip: the recoil. Each of them: the scatter it adds, degrees.
    [DataField]
    public double DamageMult = 1;

    [DataField]
    public double FireRateMult = 1;

    [DataField]
    public double RecoilMult = 1;

    [DataField]
    public double ScatterAdd;

    [DataField]
    public double FatigueShots = 2000;

    [DataField]
    public double HeatPerShotK = 10;

    [DataField]
    public double LimitTempC = 700;
}

// A platform: what a weapon made of the parts is. It says what the receiver is, which action works it, how it is fed and what the weapon is before the parts
// change it. The platform of a weapon is the platform of its receiver.
[Prototype("cmuWeaponPlatform")]
public sealed partial class WeaponPlatformPrototype : IPrototype
{
    [IdDataField]
    public string ID { get; private set; } = default!;

    [DataField(required: true)]
    public LocId Name;

    // The action of the gunsmith that works the weapon (its fire modes and its rate come from it).
    [DataField(required: true)]
    public string Action = string.Empty;

    // The caliber of the weapon (the id of a gunsmith caliber); the barrel and the bolt of the platform are made for it.
    [DataField(required: true)]
    public string Caliber = string.Empty;

    [DataField]
    public FeedKind Feed = FeedKind.Magazine;

    // The capacity of the cylinder or of the magazine inside, for a weapon that is not fed from a magazine.
    [DataField]
    public int FeedCapacity = 6;

    [DataField]
    public StockKind Stock = StockKind.Fixed;

    // What the weapon is before the parts change it.
    [DataField]
    public double BaseDamage = 20;

    [DataField]
    public double BaseVelocity = 400;

    [DataField]
    public double BaseScatter = 3;

    [DataField]
    public double BaseRecoil = 2;
}

// The bench where a weapon is put together: four slots, one for each kind of part, and a verb to assemble.
[RegisterComponent, NetworkedComponent]
public sealed partial class WeaponAssemblyBenchComponent : Component
{
    public const string BarrelSlot = "weapon_barrel";
    public const string ReceiverSlot = "weapon_receiver";
    public const string BoltSlot = "weapon_bolt";
    public const string GripSlot = "weapon_grip";

    public static readonly (WeaponPartKind Kind, string Slot)[] Slots =
    {
        (WeaponPartKind.Barrel, BarrelSlot),
        (WeaponPartKind.Receiver, ReceiverSlot),
        (WeaponPartKind.Bolt, BoltSlot),
        (WeaponPartKind.Grip, GripSlot),
    };

    // The seconds it takes to put a weapon together.
    [DataField]
    public float AssembleSeconds = 6f;
}
