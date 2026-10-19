// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2026 wray-git
using System.Linq;
using Content.Shared.CMU14.Gunsmith;

namespace Content.Shared.CMU14.WeaponParts;

// What the assembly of four parts comes to: the errors that stop it (as ids of the messages), or the numbers of the weapon.
public sealed class WeaponAssemblyResult
{
    public readonly List<string> Errors = new();

    public double Damage;
    public double MuzzleVelocity;
    public double FireRate;
    public int Modes;
    public double ScatterDegrees;
    public double RecoilFactor;
    public double Reliability;
    public double Quality;
    public double PressureMpa;
    public double WeakestSafety;
    public double StockSafety;
    public double HingeSafety;
    public double BarrelYieldMpa;
    public double BarrelMisesMpa;
    public double BarrelLimitTempC;
    public double FatigueLifeShots;
    public double HeatPerShotK;
    public double BarrelLengthMm;

    // The weakest grade of the four parts: a weapon is as good as its worst part.
    public WeaponPartGrade Grade;

    public bool Ok => Errors.Count == 0;
}

// Puts the four parts of a weapon together by simple rules, the same for the bench and for the examine text of it. A part adds its own numbers: a barrel the damage and
// the scatter, a bolt the rate, a grip the recoil; a weapon holds as much as its weakest part, and it jams as often as the parts, all together, do.
public static class WeaponAssembler
{
    public static WeaponAssemblyResult Evaluate(
        WeaponPlatformPrototype platform,
        GunsmithActionPrototype action,
        double nominalPressureMpa,
        IReadOnlyDictionary<WeaponPartKind, WeaponPartComponent> parts)
    {
        var result = new WeaponAssemblyResult();

        foreach (var kind in Enum.GetValues<WeaponPartKind>())
        {
            if (!parts.ContainsKey(kind))
                result.Errors.Add("weaponparts-error-missing-" + kind.ToString().ToLowerInvariant());
        }

        if (!result.Ok)
            return result;

        var barrel = parts[WeaponPartKind.Barrel];
        var receiver = parts[WeaponPartKind.Receiver];
        var bolt = parts[WeaponPartKind.Bolt];
        var grip = parts[WeaponPartKind.Grip];

        // The platform of the weapon is the platform of its receiver, and every other part has to be made for it.
        if (receiver.Platform != platform.ID || barrel.Platform != platform.ID || bolt.Platform != platform.ID || grip.Platform != platform.ID)
            result.Errors.Add("weaponparts-error-platform");

        if (barrel.Caliber != bolt.Caliber || barrel.Caliber != platform.Caliber)
            result.Errors.Add("weaponparts-error-caliber");

        if (!result.Ok)
            return result;

        var all = new[] { barrel, receiver, bolt, grip };

        result.Damage = platform.BaseDamage * barrel.DamageMult;
        result.MuzzleVelocity = platform.BaseVelocity * Math.Sqrt(Math.Max(0.1, barrel.DamageMult));
        result.FireRate = bolt.FireRateMult / Math.Max(0.1, action.CycleSeconds);
        result.Modes = action.Modes;
        result.ScatterDegrees = Math.Max(0.2, platform.BaseScatter + all.Sum(p => p.ScatterAdd));
        result.RecoilFactor = platform.BaseRecoil * grip.RecoilMult;
        result.Reliability = Math.Clamp(all.Aggregate(1.0, (acc, p) => acc * p.Reliability), 0.3, 1.0);
        result.Quality = 0.8 + 0.1 * all.Average(p => (double) p.Grade);
        result.Grade = all.Min(p => p.Grade);
        result.BarrelLengthMm = barrel.BarrelLengthMm;

        // How the weapon takes the shot: the pressure of the normal load of its caliber, against what the parts are worth.
        result.PressureMpa = nominalPressureMpa;
        result.WeakestSafety = new[] { barrel.Safety, receiver.Safety, bolt.Safety }.Min();
        result.StockSafety = grip.Safety;
        result.HingeSafety = receiver.Safety;
        result.BarrelMisesMpa = nominalPressureMpa;
        result.BarrelYieldMpa = nominalPressureMpa * barrel.Safety * 1.2;
        result.BarrelLimitTempC = barrel.LimitTempC;
        result.FatigueLifeShots = barrel.FatigueShots;
        result.HeatPerShotK = barrel.HeatPerShotK;
        return result;
    }
}
