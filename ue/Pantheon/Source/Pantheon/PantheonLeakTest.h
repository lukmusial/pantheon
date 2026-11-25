// -PantheonLeakTest=<file>: find holes in the building's shell that the visitor can slip through.
//
// The model's walls are shells: an inner face and an outer face several metres apart, hollow between
// (the drum, the attic, the dome, the portico's block). The test starts the visitor's capsule inside
// those hollows and floods outwards cell by cell with capsule sweeps against the level's collision;
// a flood that reaches the rotunda, the portico or the open air has found a way in, and its path is
// written out (Blender metres, as in ue/shots) so the hole can be found and closed.

#pragma once

#include "CoreMinimal.h"

class UWorld;

void RunPantheonLeakTest(UWorld* World, float CapsuleRadius, float CapsuleHalfHeight, const FString& OutFile);
