// On-screen help and a one-line status for the walk-through app (F2).

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "PantheonHUD.generated.h"

UCLASS()
class PANTHEON_API APantheonHUD : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;
};
