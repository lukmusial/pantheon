#include "PantheonLeakTest.h"

#include "CollisionQueryParams.h"
#include "Engine/World.h"
#include "HAL/PlatformTime.h"
#include "Misc/FileHelper.h"

namespace
{
	constexpr float Step = 25.0f;           // cm between cells
	constexpr int32 CellLimit = 6000000;    // per seed: enough for the whole hollow of the drum and attic

	// Blender metres (x, y up the door axis, z) to Unreal cm and back
	FVector ToUE(double X, double Y, double Z) { return FVector(X * 100.0, -Y * 100.0, Z * 100.0); }
	FVector ToBlender(const FVector& P) { return FVector(P.X / 100.0, -P.Y / 100.0, P.Z / 100.0); }

	/** Where the visitor may legitimately be, or nullptr inside the masonry's hollows. */
	const TCHAR* OpenSpace(const FVector& B)
	{
		const double R = FMath::Sqrt(B.X * B.X + B.Y * B.Y);
		const double FromCentre = FMath::Sqrt(R * R + FMath::Square(B.Z - 21.72));
		if ((R < 20.5 && B.Z < 21.0) || (B.Z >= 21.0 && FromCentre < 20.9))
		{
			return TEXT("the rotunda");
		}
		if (B.Y > 34.5)
		{
			return TEXT("the portico");
		}
		const bool bBlock = FMath::Abs(B.X) < 17.6 && B.Y > 13.0 && B.Y < 34.0;
		if (R > 30.2 && !bBlock)
		{
			return TEXT("the open air");
		}
		if (B.Z > 47.0)
		{
			return TEXT("the open air above");
		}
		return nullptr;
	}
}

void RunPantheonLeakTest(UWorld* World, float CapsuleRadius, float CapsuleHalfHeight, const FString& OutFile)
{
	TArray<FString> Lines;
	auto Say = [&Lines](const FString& S)
	{
		UE_LOG(LogTemp, Warning, TEXT("[leak] %s"), *S);
		Lines.Add(S);
	};
	const FCollisionShape Shape = FCollisionShape::MakeCapsule(CapsuleRadius, CapsuleHalfHeight);
	FCollisionQueryParams Params(TEXT("PantheonLeakTest"), true);
	auto Blocked = [&](const FVector& A, const FVector& B)
	{
		return World->SweepTestByChannel(A, B, FQuat::Identity, ECC_Pawn, Shape, Params);
	};
	auto Fits = [&](const FVector& P)
	{
		return !World->OverlapAnyTestByChannel(P, FQuat::Identity, ECC_Pawn, Shape, Params);
	};
	Say(FString::Printf(TEXT("self-test: through the rotunda wall blocked %d, across the floor blocked %d"),
		Blocked(ToUE(0, -15, 1.5), ToUE(0, -30, 1.5)) ? 1 : 0, Blocked(ToUE(-3, 0, 1.5), ToUE(3, 0, 1.5)) ? 1 : 0));

	struct FSeed { const TCHAR* Name; FVector B; };
	TArray<FSeed> Seeds;
	for (int32 k = 0; k < 8; ++k)
	{
		const double Pier = FMath::DegreesToRadians(22.5 + 45.0 * k), Axis = FMath::DegreesToRadians(45.0 * k);
		Seeds.Add({TEXT("drum wall, behind a pier"), FVector(25.0 * FMath::Cos(Pier), 25.0 * FMath::Sin(Pier), 4.0)});
		if (k != 2)   // not the doorway
		{
			Seeds.Add({TEXT("drum wall, behind a recess"), FVector(27.3 * FMath::Cos(Axis), 27.3 * FMath::Sin(Axis), 4.0)});
		}
		Seeds.Add({TEXT("attic wall"), FVector(24.8 * FMath::Cos(Pier), 24.8 * FMath::Sin(Pier), 17.0)});
	}
	for (const double El : {20.0, 50.0})
	{
		const double E = FMath::DegreesToRadians(El), A = FMath::DegreesToRadians(200.0);
		Seeds.Add({TEXT("dome shell"), FVector(22.47 * FMath::Cos(E) * FMath::Cos(A), 22.47 * FMath::Cos(E) * FMath::Sin(A), 21.72 + 22.47 * FMath::Sin(E))});
	}
	Seeds.Add({TEXT("portico block, low"), FVector(10.0, 31.0, 4.0)});
	Seeds.Add({TEXT("portico block, high"), FVector(-8.0, 30.0, 20.0)});
	Seeds.Add({TEXT("portico block, top"), FVector(12.0, 25.0, 23.5)});

	const double T0 = FPlatformTime::Seconds();
	const FIntVector Dirs[6] = {FIntVector(1, 0, 0), FIntVector(-1, 0, 0), FIntVector(0, 1, 0), FIntVector(0, -1, 0),
		FIntVector(0, 0, 1), FIntVector(0, 0, -1)};
	int32 Leaks = 0;
	TSet<FIntVector> Reported;
	for (const FSeed& Seed : Seeds)
	{
		const FVector Start = ToUE(Seed.B.X, Seed.B.Y, Seed.B.Z);
		const FString Where = FString::Printf(TEXT("%s at (%.1f, %.1f, %.1f)"), Seed.Name, Seed.B.X, Seed.B.Y, Seed.B.Z);
		if (!Fits(Start))
		{
			Say(FString::Printf(TEXT("%s: no room for the capsule there, skipped"), *Where));
			continue;
		}
		TMap<FIntVector, FIntVector> Parent;
		Parent.Reserve(1 << 20);
		Parent.Add(FIntVector::ZeroValue, FIntVector::ZeroValue);
		TArray<FIntVector> Queue;
		Queue.Add(FIntVector::ZeroValue);
		int32 Head = 0;
		const TCHAR* Escape = nullptr;
		FIntVector EscapeCell;
		auto At = [&Start](const FIntVector& K) { return Start + FVector(K) * Step; };
		while (Head < Queue.Num() && Parent.Num() < CellLimit && !Escape)
		{
			const FIntVector K = Queue[Head++];
			const FVector P = At(K);
			for (const FIntVector& D : Dirs)
			{
				const FIntVector N = K + D;
				if (Parent.Contains(N))
				{
					continue;
				}
				const FVector PN = At(N);
				if (PN.Z < CapsuleHalfHeight + 2.0 || PN.Z > 5000.0 || Blocked(P, PN))
				{
					continue;
				}
				Parent.Add(N, K);
				Queue.Add(N);
				if (const TCHAR* Open = OpenSpace(ToBlender(PN)))
				{
					Escape = Open;
					EscapeCell = N;
					break;
				}
			}
		}
		if (!Escape)
		{
			Say(FString::Printf(TEXT("%s: sealed (%d cells%s)"), *Where, Parent.Num(), Parent.Num() >= CellLimit ? TEXT(", limit") : TEXT("")));
			continue;
		}
		++Leaks;
		// the way out, from the seed: the last cells inside the masonry are where the hole is
		TArray<FIntVector> Path;
		for (FIntVector K = EscapeCell; ; K = Parent[K])
		{
			Path.Insert(K, 0);
			if (K == FIntVector::ZeroValue)
			{
				break;
			}
		}
		FString Trail;
		const int32 From = FMath::Max(0, Path.Num() - 24);
		for (int32 i = From; i < Path.Num(); i += 2)
		{
			const FVector B = ToBlender(At(Path[i]));
			Trail += FString::Printf(TEXT(" (%.2f, %.2f, %.2f)"), B.X, B.Y, B.Z);
		}
		Say(FString::Printf(TEXT("%s: LEAK into %s after %d cells, path length %d; its last steps:%s"),
			*Where, Escape, Parent.Num(), Path.Num(), *Trail));
	}
	Say(FString::Printf(TEXT("%d of %d seeds leak (%.0f s)"), Leaks, Seeds.Num(), FPlatformTime::Seconds() - T0));
	FFileHelper::SaveStringArrayToFile(Lines, *OutFile);
}
