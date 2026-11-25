#include "PantheonHUD.h"

#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "PantheonVisitor.h"

namespace
{
	const TCHAR* const Help[] = {
		TEXT("THE PANTHEON, c. 126 AD"),
		TEXT(""),
		TEXT("W A S D / arrows     walk"),
		TEXT("Mouse                look"),
		TEXT("Shift                faster"),
		TEXT("F                    fly / walk"),
		TEXT("E / Space, Q / C     up, down (flying); Space jumps when walking"),
		TEXT("Mouse wheel, + -     zoom (up to 15x)"),
		TEXT("Right mouse / Z      hold to look closer"),
		TEXT("Tab                  next viewpoint"),
		TEXT("[ ]                  darker, brighter"),
		TEXT("R                    reset zoom and brightness"),
		TEXT("1 2 3                quality: smooth, balanced, detailed"),
		TEXT("G                    ghosts in the fog on / off"),
		TEXT("H                    show / hide this help"),
		TEXT("Esc                  quit"),
	};
}

void APantheonHUD::DrawHUD()
{
	Super::DrawHUD();
	const APantheonVisitor* Visitor = Cast<APantheonVisitor>(GetOwningPawn());
	if (!Visitor || !Canvas || Visitor->IsFilming())   // nothing over the picture while a film is recorded
	{
		return;
	}
	UFont* Font = GEngine->GetMediumFont();
	const float Scale = FMath::Max(1.0f, Canvas->ClipY / 1080.0f);
	const float Line = 22.0f * Scale;
	const float X = 40.0f * Scale;

	if (Visitor->bShowHelp)
	{
		const int32 Lines = UE_ARRAY_COUNT(Help);
		const float Top = 40.0f * Scale;
		DrawRect(FLinearColor(0.0f, 0.0f, 0.0f, 0.55f), X - 16.0f * Scale, Top - 12.0f * Scale, 640.0f * Scale, Lines * Line + 24.0f * Scale);
		for (int32 i = 0; i < Lines; ++i)
		{
			DrawText(Help[i], FLinearColor(0.95f, 0.9f, 0.8f), X, Top + i * Line, Font, Scale);
		}
	}

	static const TCHAR* const Quality[] = {TEXT("smooth"), TEXT("balanced"), TEXT("detailed")};
	const FString Status = FString::Printf(TEXT("%s   |   %s   |   zoom %.1fx   |   exposure %+.1f EV%s   |   quality %s   |   H help"),
		*Visitor->GetViewpointName(), Visitor->IsFlying() ? TEXT("flying") : TEXT("walking"), Visitor->GetZoom(),
		Visitor->GetExposure(), Visitor->GetExposureOffset() != 0.0f ? *FString::Printf(TEXT(" (%+.1f)"), Visitor->GetExposureOffset()) : TEXT(""),
		Quality[FMath::Clamp(Visitor->GetQualityLevel(), 1, 3) - 1]);
	DrawText(Status, FLinearColor(0.95f, 0.9f, 0.8f, 0.8f), X, Canvas->ClipY - 50.0f * Scale, Font, Scale);
}
