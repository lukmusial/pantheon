// F3 "ghosts in the fog" in the walk-through app.
//
// With bSpawnScene the driver brings the whole scene: a thin floor fog over the rotunda
// (/Game/F3Runtime/MI_GhostFog on a box) and five ghosts (user, 2026-11-23):
//   - four worshippers, two men and two women, go from god to god round the rotunda: each walks
//     slowly, hands clasped before them and head a little bowed, to the altar in front of a statue,
//     kneels there with head bowed for a while, rises and moves on;
//   - a priest before Jupiter raises his hands standing (the Roman gesture of prayer), lowers them,
//     kneels with head bowed for longer, and stands up again, over and over.
//
// A ghost is not a mesh. Each tick the driver poses a skeleton (the UE5 mannequin's, never drawn):
// the idle animation for the trunk, bowing laid over it as bone rotations, the arms placed by
// two-bone IK so the hands are clasped, joined in prayer or raised, and the legs by IK too: the
// figure moves at an even, eased speed and each foot stays where it was set down until it is lifted
// for the next step (user, 2026-11-24: the movement was jumpy and must be smooth). Around the
// joints it lays tapered capsules that describe a figure in plain Roman dress (a toga, a woman's
// long tunic with the palla draped the same way, a knee-length tunic), different for each ghost in
// height, girth, shoulder width and stoop, followed by the trail: fading, widening, drifting puffs where
// the figure has just been. The capsules go into a small float texture (three rows per ghost: end A
// and radius, end B and radius, strength / kind / pad / noise; world cm), which the material
// /Game/F3Runtime/MI_GhostMist marches as a volume of mist (pantheon_materials.build_ghost_mist).
// That material runs on a camera-facing quad per ghost, kept on the near side of the ghost's
// bounding sphere, or just in front of the camera when the camera is inside it.
//
// While the ghosts are about, the statues' painted eyes follow the visitor: see FollowWithStatueEyes.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "F3GhostDriver.generated.h"

class AStaticMeshActor;
class UAnimSequence;
class UMaterialInstanceDynamic;
class UMaterialInterface;
class UStaticMeshComponent;
class USkeletalMesh;
class UTexture2D;
struct FBoneContainer;

UCLASS()
class PANTHEON_API AF3GhostDriver : public AActor
{
	GENERATED_BODY()

public:
	AF3GhostDriver();

	virtual void Tick(float DeltaSeconds) override;

	/** Spawn the fog volume and the ghosts (the app). Without it the driver does nothing. */
	UPROPERTY(EditAnywhere, Category = "F3")
	bool bSpawnScene = false;

	/** Seconds the ghosts have already been about when they appear: a film sets it, to choose where
	 * each of them is at a given moment (their movements are the same on every run). */
	UPROPERTY(EditAnywhere, Category = "F3")
	float PrerollSeconds = 0.0f;
	/** And the priest that much longer still (his round of prayer does not depend on the others). */
	UPROPERTY(EditAnywhere, Category = "F3")
	float PriestPrerollSeconds = 0.0f;

	/** Where a ghost stands (its feet, world cm) and how tall it is; false if there is no such ghost.
	 * 0-3 are the worshippers (citizen, matron, old man, young woman), 4 the priest. */
	bool GetGhostPlace(int32 Index, FVector& OutFeet, float& OutHeight) const;

	/** Walking speed (cm/s) of the worshippers: slow, in pious reverence. Each build scales it. */
	UPROPERTY(EditAnywhere, Category = "F3")
	float WalkSpeed = 55.0f;

	/** How long a worshipper stays on their knees at an altar (s, chosen between the two). */
	UPROPERTY(EditAnywhere, Category = "F3")
	float KneelSecondsMin = 10.0f;
	UPROPERTY(EditAnywhere, Category = "F3")
	float KneelSecondsMax = 18.0f;

	/** The trail: a puff is left every TrailInterval seconds and lives TrailSeconds. */
	UPROPERTY(EditAnywhere, Category = "F3")
	float TrailInterval = 0.6f;
	UPROPERTY(EditAnywhere, Category = "F3")
	float TrailSeconds = 6.0f;

	/** Drift of the trail (cm/s), how much a puff widens over its life (1 = doubles) and its
	 * strength when new (the body is 1). */
	UPROPERTY(EditAnywhere, Category = "F3")
	FVector Wind = FVector(2.0, 3.0, 2.0);
	UPROPERTY(EditAnywhere, Category = "F3")
	float TrailGrowth = 1.1f;
	UPROPERTY(EditAnywhere, Category = "F3")
	float TrailStrength = 1.0f;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
	/** A tapered capsule of mist, as the material reads it. */
	struct FPrim
	{
		FVector A;
		FVector B;
		float RA;
		float RB;
		float Strength;
		float Kind;    // 0 body (melts into its neighbours), 1 trail puff
		float Pad;     // how far beyond the surface the mist can reach (cm)
		float Noise;   // trail: how far the noise moves the edge (cm)
	};

	/** A pose weight that eases towards its target (critically damped). */
	struct FEase
	{
		float Value = 0.0f;
		float Velocity = 0.0f;
		float Target = 0.0f;
		void Step(float Dt, float SmoothTime);
		void Set(float V) { Value = Target = V; Velocity = 0.0f; }
	};

	enum class EGhostState : uint8
	{
		Walk, Arrive, KneelDown, Kneel, Rise,                    // worshippers
		PriestStand, PriestOrans, PriestLower, PriestKneel, PriestRise
	};

	/** Bones the poses use (mesh bone indices) and measures of the reference pose. */
	struct FRig
	{
		int32 Root = INDEX_NONE;
		int32 Pelvis = INDEX_NONE;
		int32 Spine[5] = {INDEX_NONE, INDEX_NONE, INDEX_NONE, INDEX_NONE, INDEX_NONE};
		int32 Neck = INDEX_NONE;
		int32 Head = INDEX_NONE;
		int32 Thigh[2] = {INDEX_NONE, INDEX_NONE};
		int32 Calf[2] = {INDEX_NONE, INDEX_NONE};
		int32 Foot[2] = {INDEX_NONE, INDEX_NONE};
		int32 Ball[2] = {INDEX_NONE, INDEX_NONE};
		int32 UpperArm[2] = {INDEX_NONE, INDEX_NONE};
		int32 LowerArm[2] = {INDEX_NONE, INDEX_NONE};
		int32 Hand[2] = {INDEX_NONE, INDEX_NONE};
		float KneelDrop = 45.0f;       // how far the pelvis comes down when kneeling (cm)
		float KneelBack = 26.0f;       // and how far behind the hip the ankle then lies
		float ThighLength = 42.0f;
		float CalfLength = 42.0f;
		float HipX = 9.0f;             // the hip joints' distance from the middle
		float HipZ = 95.0f;            // their height, the ankles' and the balls of the feet's, standing
		float AnkleZ = 8.0f;
		float BallZ = 2.5f;
		float FootLength = 14.0f;      // ankle to the ball of the foot
		float UpperArmLength = 28.0f;
		float ForeArmLength = 27.0f;
		FVector HeadUpLocal = FVector::UpVector;        // the figure's up and forward, in the head bone's space
		FVector HeadForwardLocal = FVector::ForwardVector;
		bool bValid = false;
	};

	/** A foot on the floor: where it stands (world cm), or its flight to the next place. */
	struct FFoot
	{
		FVector2D Pos = FVector2D::ZeroVector;
		float Yaw = 0.0f;
		FVector2D From = FVector2D::ZeroVector;   // where the step in flight began
		float FromYaw = 0.0f;
		float U = 1.0f;       // how far through the step (1 = on the ground)
		float Lift = 0.0f;    // height above the floor (cm)
	};

	struct FPuff
	{
		float Time;
		FVector Base;
		FVector Top;
		float Scale;
		float Strength;
	};

	struct FGhost
	{
		TWeakObjectPtr<AStaticMeshActor> Quad;
		TWeakObjectPtr<UMaterialInstanceDynamic> Mist;
		int32 Build = 0;
		bool bPriest = false;
		FVector Position = FVector::ZeroVector;   // feet, cm
		float Yaw = 0.0f;                         // the way the figure faces (degrees)
		float YawRate = 0.0f;
		float Speed = 0.0f;                       // along the path (cm/s), eased
		FVector2D Velocity = FVector2D::ZeroVector;
		TArray<FVector> Path;
		TArray<float> PathLength;
		float PathPos = 0.0f;
		int32 Station = 0;
		int32 Target = 0;
		EGhostState State = EGhostState::Kneel;
		float StateTime = 0.0f;
		float Hold = 0.0f;
		FFoot Feet[2];           // left, right
		float GaitClock = 0.0f;  // in step cycles: the left foot lifts at 0, the right at 0.5
		bool bGaitActive = false;
		bool bFeetKnown = false;
		int32 FirstFoot = 0;     // the foot that leads off next time
		float IdleTime = 0.0f;
		FEase Kneel, Bow, Orans;
		mutable FVector TraceHand[2] = {FVector::ZeroVector, FVector::ZeroVector};   // for -PantheonGhostTrace
		mutable FVector TracePelvis = FVector::ZeroVector;
		FRandomStream Rand;
		TArray<FTransform> Local;   // bone transforms, relative to the parent
		TArray<FTransform> CS;      // and in the figure's own space (faces +Y, left +X, up +Z; unscaled)
		TArray<FPuff> Trail;
		float LastPuff = -1e9f;
	};

	struct FStation
	{
		FVector Kneel;   // where a worshipper kneels, cm
		FVector Aisle;   // the point on the processional ring opposite
		float Azimuth;   // Blender degrees, from +Y (the door) clockwise seen from above
		float FaceYaw;   // UE yaw facing the statue
	};

	void SpawnScene();
	void FollowWithStatueEyes();
	bool InitRig();
	void SpawnGhost(int32 Index, bool bPriest);
	void StepGhost(FGhost& G, float Dt);
	void StepWorshipper(FGhost& G, float Dt);
	void StepPriest(FGhost& G, float Dt);
	void StepFeet(FGhost& G, float Dt) const;
	void PlanPath(FGhost& G, int32 From, int32 To);
	bool StationFree(const FGhost& G, int32 S) const;
	void PoseGhost(FGhost& G) const;
	void BuildBody(const FGhost& G, TArray<FPrim>& Out) const;
	void BuildTrail(FGhost& G, float Time, const FVector& Head, TArray<FPrim>& Out) const;
	void PlaceQuad(FGhost& G, const TArray<FPrim>& Prims, bool bCamera, const FVector& Camera, const FVector& CameraForward) const;

	/** A statue's material slot as it was before its eyes began to follow the visitor. */
	struct FStatueLook
	{
		TWeakObjectPtr<UStaticMeshComponent> Component;
		int32 Slot = 0;
		TWeakObjectPtr<UMaterialInterface> Original;
	};
	TArray<FStatueLook> StatueLooks;

	TArray<FGhost> Ghosts;
	TArray<FStation> Stations;
	TArray<TWeakObjectPtr<AActor>> Spawned;
	FRig Rig;
	TSharedPtr<FBoneContainer> Bones;

	UPROPERTY(Transient)
	TObjectPtr<USkeletalMesh> SkeletonMesh;
	UPROPERTY(Transient)
	TObjectPtr<UAnimSequence> IdleAnim;
	UPROPERTY(Transient)
	TObjectPtr<UTexture2D> PrimTexture;

	// -PantheonGhostTrace=<file>: every tick's positions of each ghost, to measure how even the motion is
	FString TraceFile;
	TArray<FString> TraceLines;
	void FlushTrace();

	float LastTime = -1.0f;
	int32 LogCounter = 0;
	bool bSolid = false;
	bool bLineup = false;
	bool bNoMist = false;
	bool bReady = false;
};
